# coding=utf-8

import numpy as np
import os
import torch
from sklearn.metrics import accuracy_score
from sklearn.metrics import precision_score
from sklearn.metrics import recall_score
from sklearn.metrics import f1_score
from sklearn.metrics import confusion_matrix
from torch.utils.data import DataLoader
from tqdm import tqdm

from utils import save_checkpoint
from utils import generate_plots


# Use GPU if available, otherwise use CPU.
USE_CUDA = torch.cuda.is_available()

def train(model, loss_fn, optimizer, history, trainset, valset, config):
    """ Trains the model by optimizing with respect to the given loss
        function using the given optimizer.

        Args:
            model: torch.nn.Module 
                Defines the model.
            loss_fn: torch.nn.Module 
                Defines the loss function.
            optimizer: torch.optim.optimizer 
                Defines the optimizer.
            history: dict
                Contains histories of desired run metrics.
            trainset: torch.utils.data.Dataset 
                Contains the training data.
            valset: torch.utils.data.Dataset 
                Contains the validation data.
            config: dict
                Configures the training loop. Contains the following keys:

                batch_size: int
                    The number of examples to process per batch.
                    Default value is 64.
                start_epoch: int
                    The epoch to start on for training.
                    Default value is 1.
                num_epochs: int
                    How many epochs to train the model.
                    Default value is 20.
                log_every: int
                    How often to save model checkpoints and generate
                    plots. To turn off logging, set this value to 0.
                    Default value is 5.
                num_workers: int
                    How many works to assign to the DataLoader.
                    Default value is 4.

        Returns:
            model: a torch.nn.Module defining the trained model.
    """

    # Get keyword parameter values
    batch_size = config.get("batch_size", 20)
    start_epoch = config.get("start_epoch", 1)
    num_epochs = config.get("num_epochs", 20)
    log_every = config.get("log_every", 5)
    num_workers = config.get("num_workers", 4)
    checkpoint_dir = config.get("checkpoint_dir", "checkpoints")

    # Use the f1 score to determine best checkpoint
    best_val_f1 = 0 

    # Training loop
    for epoch in tqdm(range(start_epoch, num_epochs + 1), desc="Epochs", position=0):

        # Process training dataset
        model, train_results, train_cm = \
            process_batches(model, trainset, loss_fn, batch_size, num_workers, 
                            desc="train", optimizer=optimizer, is_training=True)
        tqdm.write(
            """
            Confusion Matrix: {} \n
            Macro-level Accuracy: {} \n
            Macro-level Precision: {} \n
            Macro-level Recall: {} \n
            Macro-level F1: {}
            """
            .format(
                np.array_str(train_cm),
                train_results["accuracy"],
                train_results["precision"],
                train_results["recall"],
                train_results["f1"]
            )
        )
    
        # Process validation dataset
        val_results, val_cm = \
            process_batches(model, valset, loss_fn, batch_size, num_workers, 
                            desc="val", optimizer=optimizer, is_training=False)
        tqdm.write(
            """
            Confusion Matrix: {} \n
            Macro-level Accuracy: {} \n
            Macro-level Precision: {} \n
            Macro-level Recall: {} \n
            Macro-level F1: {}
            """
            .format(
                np.array_str(val_cm),
                val_results["accuracy"],
                val_results["precision"],
                val_results["recall"],
                val_results["f1"]
            )
        )

        # Update run history
        for name, val in train_results.items(): 
            history["train_{}".format(name)].append(val)
        for name, val in val_results.items():
            history["val_{}".format(name)].append(val)

        # Update best checkpoint
        if val_results["f1"] > best_val_f1:
            tqdm.write("New best checkpoint!")
            best_val_f1 = val_results["f1"]
            filepath = os.path.join(checkpoint_dir, "best_checkpoint")
            save_checkpoint(model, optimizer, history, epoch, filepath)

        # Generate plots and save checkpoint
        if log_every != 0 and epoch % log_every == 0:
            print("saving checkpoint...")
            filename = "checkpoint_epoch_{}".format(epoch)
            filepath = os.path.join(checkpoint_dir, filename)
            save_checkpoint(model, optimizer, history, epoch, filepath)
            generate_plots(history, checkpoint_dir)

    return model


def evaluate(model, dataset, loss_fn, batch_size=64, num_workers=4, desc="eval"):
    """ Simple wrapper function for process_batches to evaluate the model 
        the given dataset. 
    """
    results, cm = process_batches(model, dataset, loss_fn, batch_size, 
                                    num_workers, desc)
    print(
        """
        Confusion Matrix: {} \n
        Macro-level Accuracy: {} \n
        Macro-level Precision: {} \n
        Macro-level Recall: {} \n
        Macro-level F1: {}
        """
        .format(
            np.array_str(cm),
            results["accuracy"],
            results["precision"],
            results["recall"],
            results["f1"]
        )
    )
    return results, cm


def process_batches(model, dataset, loss_fn, batch_size=64, num_workers=4, desc=None, 
                    optimizer=None, is_training=False):
    """ Processes the examples in the dataset in batches. If the dataset is the
        training set, then the model weights will be updated.

        Args:
            model: torch.nn.Module
                Defines the model.
            dataset: torch.utils.data.Dataset
                Contains the examples to process.
            loss_fn: torch.nn.Module
                Defines the loss function. The loss function takes batches
                of scores and targets and returns a batch of losses.
            batch_size: int
                The number of examples to process per batch.
                Default value is 64.
            num_workers: int
                How many workers to assign to the DataLoader.
                Default value is 4.
            desc: string
                Optional, writes a short description at the front of the
                progress bar.
            optimizer: torch.optim.optimizer
                Optional, defines the optimizer. Only required for training.
                By default, this is None.
            is_training: boolean
                Optional, specifies whether or not to update model weights.
                By default, this is False.

        Returns:
            model: torch.nn.Module
                The updated model. Returned only if is_training is True.
            results: dict
                Contains relevant evaluation metrics for the model.
            cm: np.array
                The confusion matrix for the model on the dataset.
    """
    # Track loss across all batches
    total_loss = 0

    # Track number of correct and incorrect predictions
    actual = []
    predicted = []

    # Process batches
    dataloader = \
        DataLoader(dataset, batch_size=batch_size, shuffle=True, 
                    num_workers=num_workers)
    for features, targets in tqdm(dataloader, desc=desc, position=1):

        # Load batch to GPU
        if USE_CUDA:
            torch.cuda.empty_cache()
            features = features.cuda()
            targets = targets.cuda()

        # Forward pass
        scores = model(features)
        predictions = torch.argmax(scores, dim=1)

        # Store actual and predicted labels
        actual.extend(targets.cpu().tolist())
        predicted.extend(predictions.cpu().tolist())

        # Update loss
        batch_loss = torch.sum(loss_fn(scores, targets))
        total_loss += float(batch_loss)

        # Backward pass
        if is_training:
            optimizer.zero_grad()
            batch_loss.backward()
            optimizer.step()     

    # Compute evaluation metrics
    loss = total_loss / len(dataset)
    accuracy = accuracy_score(actual, predicted)  
    precision = precision_score(actual, predicted, average="macro")
    recall = recall_score(actual, predicted, average="macro")
    f1 = f1_score(actual, predicted, average="macro")

    # Generate confusion matrix
    cm = confusion_matrix(actual, predicted, labels=[0, 1])

    # Store the results
    results = {
        "loss": loss,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
    
    if is_training:
        return model, results, cm
    return results, cm
