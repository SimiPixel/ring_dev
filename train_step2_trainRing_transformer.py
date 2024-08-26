import os

os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

import fire
import numpy as np
import ring
from ring import ml
import wandb

import dataloader
from transformer import make_transformer


def _transform(data: list, rng):
    # [dict, dict] -> dict, dict
    X_dict, y_dict = data[0]

    X = np.zeros((6000, 2, 9))
    X[:, 0, :3] = X_dict["seg4_3Seg"]["acc"]
    X[:, 0, 3:6] = X_dict["seg4_3Seg"]["gyr"]
    X[:, 0, 6:9] = X_dict["seg4_3Seg"]["joint_axes"]
    X[:, 1, :3] = X_dict["seg5_3Seg"]["acc"]
    X[:, 1, 3:6] = X_dict["seg5_3Seg"]["gyr"]
    X[:, 1, 6:9] = X_dict["seg5_3Seg"]["joint_axes"]

    y = np.zeros((6000, 2, 4))
    y[:, 0, :] = y_dict["seg4_3Seg"]
    y[:, 1, :] = y_dict["seg5_3Seg"]
    return X, y


def _make_net(dry_run: bool):
    net = make_transformer(
        embed_dim=32 if dry_run else 512, ff_dim=32 if dry_run else 2048
    )
    return net


def main(
    path_lam3,
    bs: int,
    episodes: int,
    path_trained_params: str | None = None,
    use_wandb: bool = False,
    wandb_project: str = "RING",
    wandb_name: str = None,
    seed: int = 1,
    dry_run: bool = False,
    dl_worker_count: int = 0,
    dl_backend: str = "eager",
    lr: float = 1e-3,
):

    np.random.seed(seed)

    if use_wandb:
        wandb.init(project=wandb_project, config=locals(), name=wandb_name)

    if path_trained_params is None:
        path_trained_params = f"~/params/{ring.ml.unique_id()}.pickle"

    ringnet = _make_net(dry_run)

    kwargs = {}
    if dl_backend != "eager":
        keyword = "num_workers" if dl_backend == "torch" else "worker_count"
        kwargs.update({keyword: dl_worker_count})
    generator = dataloader.make_generator(
        path_lam3,
        batch_size=bs,
        transform=_transform,
        seed=seed,
        backend=dl_backend,
        **kwargs,
    )

    optimizer = ml.make_optimizer(
        lr,
        episodes,
        n_steps_per_episode=6,
        skip_large_update_max_normsq=100.0,
    )

    ml.train_fn(
        generator,
        episodes,
        ringnet,
        optimizer=optimizer,
        callback_kill_after_seconds=23.5 * 3600,
        callback_kill_if_nan=True,
        callback_kill_if_grads_larger=1e32,
        callback_save_params=path_trained_params,
        seed_network=seed,
        link_names=[
            "seg4_3Seg",
            "seg5_3Seg",
        ],
    )

    print(f"Trained parameters saved to {path_trained_params}")


if __name__ == "__main__":
    fire.Fire(main)
