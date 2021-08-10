import torch
import sys
import json
import os
import argparse
import random
import numpy as np
from torch.backends import cudnn
from utils.file import prepare_dirs, list_sub_folders
from munch import Munch
from utils.misc import get_datetime, str2bool, get_commit_hash
from utils.file import save_json


def setup_cfg(args):
    cudnn.benchmark = args.cudnn_benchmark
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)

    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

    if args.debug:
        print("Warning: running in debug mode, some settings will be override.")
        args.exp_id = "debug"
        args.sample_every = 10
        args.eval_every = 20
        args.save_every = 20
        args.end_iter = args.start_iter + 60
    if os.name == 'nt' and args.num_workers != 0:
        print("Warning: reset num_workers = 0, because running on a Windows system.")
        args.num_workers = 0

    args.log_dir = os.path.join(args.exp_dir, args.exp_id, "logs")
    args.sample_dir = os.path.join(args.exp_dir, args.exp_id, "samples")
    args.model_dir = os.path.join(args.exp_dir, args.exp_id, "models")
    args.eval_dir = os.path.join(args.exp_dir, args.exp_id, "eval")
    prepare_dirs([args.log_dir, args.sample_dir, args.model_dir, args.eval_dir])
    args.record_file = os.path.join(args.exp_dir, args.exp_id, "records.txt")
    args.loss_file = os.path.join(args.exp_dir, args.exp_id, "losses.csv")

    args.domains = list_sub_folders(args.train_path, full_path=False)
    args.num_domains = len(args.domains)


def validate_cfg(args):
    assert args.eval_every % args.save_every == 0
    assert args.num_domains == len(list_sub_folders(args.test_path, full_path=False))
    if args.cache_dataset:
        assert args.preload_dataset, "Use cached dataset requires you enable preloading dataset!"


def load_cfg():
    # There are two ways to load config, use a json file or command line arguments.
    if len(sys.argv) >= 2 and sys.argv[1].endswith('.json'):
        with open(sys.argv[1], 'r') as f:
            cfg = json.load(f)
            cfg = Munch(cfg)
            if len(sys.argv) >= 3:
                cfg.exp_id = sys.argv[2]
            else:
                print("Warning: using existing experiment dir.")
            if not cfg.about:
                cfg.about = f"Copied from: {sys.argv[1]}"
    else:
        cfg = parse_args()
        cfg = Munch(cfg.__dict__)
        if not cfg.hash:
            cfg.hash = get_commit_hash()
    current_hash = get_commit_hash()
    if current_hash != cfg.hash:
        print(f"Warning: unmatched git commit hash: `{current_hash}` & `{cfg.hash}`.")
    return cfg


def save_cfg(cfg):
    exp_path = os.path.join(cfg.exp_dir, cfg.exp_id)
    os.makedirs(exp_path, exist_ok=True)
    filename = cfg.mode
    if cfg.mode == 'train' and cfg.start_iter != 0:
        filename = "resume"
    save_json(exp_path, cfg, filename)


def print_cfg(cfg):
    print(json.dumps(cfg, indent=4))


def parse_args():
    parser = argparse.ArgumentParser()

    # About this experiment.
    parser.add_argument('--about', type=str, default="")
    parser.add_argument('--hash', type=str, required=False, help="Git commit hash for this experiment.")
    parser.add_argument('--exp_id', type=str, default=get_datetime(), help='Folder name and id for this experiment.')
    parser.add_argument('--exp_dir', type=str, default='expr')

    # Meta arguments.
    parser.add_argument('--debug', type=str2bool, default=False)
    parser.add_argument('--mode', type=str, default='train', choices=['train', 'eval', 'sample'])
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu')

    # Model related arguments.
    parser.add_argument('--img_size', type=int, default=128)
    parser.add_argument('--latent_dim', type=int, default=16)
    parser.add_argument('--style_dim', type=int, default=64)

    # Dataset related arguments.
    parser.add_argument('--dataset', type=str, required=True)
    parser.add_argument('--npz_path', type=str)
    parser.add_argument('--npz_image_root', type=str)
    parser.add_argument('--preload_dataset', type=str2bool, default=False, help='load entire dataset into memory')
    parser.add_argument('--cache_dataset', type=str2bool, default=False, help='generate & use cached dataset')

    # Training related arguments
    parser.add_argument('--parameter_init', type=str, default='he', choices=['he', 'default'])
    parser.add_argument('--start_iter', type=int, default=0)
    parser.add_argument('--end_iter', type=int, default=100000)
    parser.add_argument('--num_workers', type=int, default=4)
    parser.add_argument('--train_path', type=str, required=True)
    parser.add_argument('--num_domains', type=int)
    parser.add_argument('--domains', type=str, nargs='+')

    # Sampling related arguments
    parser.add_argument('--sample_id', type=str)
    parser.add_argument('--sample_non_ema', type=str2bool, default=True,
                        help='Whether we use the non-ema version model to sample?')

    # Evaluation related arguments
    parser.add_argument('--eval_iter', type=int, default=0, help='Use which iter to evaluate.')
    parser.add_argument('--keep_all_eval_samples', type=str2bool, default=False)
    parser.add_argument('--keep_best_eval_samples', type=str2bool, default=True)
    parser.add_argument('--eval_repeat_num', type=int, default=1)
    parser.add_argument('--eval_batch_size', type=int, default=32)
    parser.add_argument('--test_path', type=str, required=True)
    parser.add_argument('--eval_path', type=str, required=True, help="compare with those images")
    parser.add_argument('--eval_cache', type=str2bool, default=True, help="Cache what can be safely cached")
    parser.add_argument('--selected_path', type=str, required=False,
                        help="Every time we sample, we will translate the images in this path")

    # Optimizing related arguments.
    parser.add_argument('--lr', type=float, default=1e-4, help="Learning rate for generator.")
    parser.add_argument('--d_lr', type=float, default=1e-4, help="Learning rate for discriminator.")
    parser.add_argument('--beta1', type=float, default=0.0)
    parser.add_argument('--beta2', type=float, default=0.99)
    parser.add_argument('--weight_decay', type=float, default=1e-4)
    parser.add_argument('--batch_size', type=int, default=8)
    parser.add_argument('--ema_beta', type=float, default=0.999)

    # Loss hyper arguments.
    parser.add_argument('--lambda_adv', type=float, default=1)

    # Step related arguments.
    parser.add_argument('--log_every', type=int, default=10)
    parser.add_argument('--sample_every', type=int, default=1000)
    parser.add_argument('--save_every', type=int, default=5000)
    parser.add_argument('--eval_every', type=int, default=5000)

    # Log related arguments.
    parser.add_argument('--use_tensorboard', type=str2bool, default=False)
    parser.add_argument('--save_loss', type=str2bool, default=True)

    # Others
    parser.add_argument('--seed', type=int, default=0, help='Seed for random number generator.')
    parser.add_argument('--cudnn_benchmark', type=str2bool, default=True)
    parser.add_argument('--keep_all_models', type=str2bool, default=False)

    return parser.parse_args()
