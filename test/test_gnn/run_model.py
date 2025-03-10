import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import torch
import torch.nn.functional as F
from tqdm import tqdm
from datetime import datetime
import numpy as np

from dse4wse.gnn.dataloader import NoCeptionDataset
from dse4wse.gnn.model import NoCeptionNet
from dse4wse.utils import logger

CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'checkpoint')
if not os.path.exists(CHECKPOINT_DIR):
    os.mkdir(CHECKPOINT_DIR)

def get_dataset(training=True):
    dataset = NoCeptionDataset(save_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'train' if training else 'test'))
    return dataset

def get_model(gnn_params, save_path=None):
    model = NoCeptionNet(**gnn_params)
    if save_path:
        assert os.path.exists(save_path)
        model = torch.load(save_path)
    # for name, param in model.named_parameters():
    #     assert checkpoint['model_state_dict'][name] == param
        # logger.debug(name)
        # logger.debug(param)
    return model

def train_model(model, dataset, batch_size=8):
    NUM_EPOCH = 150
    model.train()
    
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    checkpoint_path = os.path.join(CHECKPOINT_DIR, f"model_{timestamp}.pth")
    logger.info(f"Model checkpoint path: {checkpoint_path}")

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    lr_schduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.5, patience=7, threshold=1e-3)

    for epoch in range(NUM_EPOCH):
        total_loss = 0
        i = 0

        tqdm_bar = tqdm(dataset)
        for data in tqdm_bar:
            i += 1
            logits = model(data['graph'])
            # loss = F.mse_loss(logits, label)
            loss = F.smooth_l1_loss(logits, data['label'])
            loss.backward()
            total_loss += loss.item()
            tqdm_bar.set_description(f"avg loss: {total_loss / i}")

            if i % batch_size == 0:
                # torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1)
                for name, param in model.named_parameters():
                    param.grad /= batch_size
                optimizer.step()
                optimizer.zero_grad()

        lr_schduler.step(total_loss / len(dataset))

        logger.info(f"Epoch {epoch}:")
        logger.info(f"learning rate: {lr_schduler._last_lr}")
        logger.info(f"average loss: {total_loss / len(dataset)}")

        # if True:
        if (epoch + 1) % 5 == 0:
            # model.eval()
            # test_model(model, get_dataset(training=True))
            # test_model(model, get_dataset(training=False))
            # model.train()
            torch.save(model, checkpoint_path)
            
            # reload the model
            # model = torch.load(checkpoint_path)
            # model.eval()
            # test_model(model, get_dataset(training=False))
            # model.train()
        if (epoch + 1) % 15 == 0:
            model.eval()
            test_model(model, get_dataset(training=False))
            model.train()


def test_model(model, dataset):
    total_mae = []
    total_mape = []

    with torch.no_grad():
        for data in tqdm(dataset):
            logits = model(data['graph'])
            label = data['label']
            mae = torch.abs(logits - label)
            mape = mae / label
            total_mae.append(mae.item())
            total_mape.append(mape.item())
            # logger.debug(f"MAE: {mae}")
    
    avg_mae = np.mean(total_mae)
    avg_mape = np.mean(total_mape)

    logger.info(f"Overall MAE: {avg_mae}")
    logger.info(f"Overall MAPE: {avg_mape}")

def run(gnn_params={}):
    # model = get_model(gnn_params)

    gnn_params = {
        'h_dim': 128,
        'n_layer': 3,
        'use_deeper_mlp_for_inp': True,
        'use_deeper_mlp_for_edge_func': True,
        'pooling': 'set2set',
    }
    # model = get_model(gnn_params, os.path.join(CHECKPOINT_DIR, "model_2023-04-27-13-56-22-753945.pth"))
    model = get_model(gnn_params)

    train_model(model, get_dataset(training=True))  # smaller dataset for debugging

    # model.eval()
    # test_model(model, get_dataset(training=False))

if __name__ == "__main__":
    run()