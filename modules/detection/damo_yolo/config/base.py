#!/usr/bin/env python3
# Copyright (C) Alibaba Group Holding Limited. All rights reserved.

import importlib
import os
import sys
from abc import ABCMeta


class AttrDict(dict):
    """Dict that can access keys as attributes"""
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        
        # Convert nested dictionaries to AttrDict
        for key, value in self.items():
            if isinstance(value, dict) and not isinstance(value, AttrDict):
                self[key] = AttrDict(value)
            # Don't try to convert None or non-dict values
        
        # Create separate __dict__ attribute instead of self-reference
        object.__setattr__(self, '__dict__', self)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'AttrDict' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        # Convert dict to AttrDict when setting attributes
        if isinstance(value, dict) and not isinstance(value, AttrDict):
            value = AttrDict(value)
        self[name] = value

    def copy(self):
        return AttrDict(super().copy())
        
    # Add this method to exclude __dict__ when being passed as kwargs
    def items(self):
        for key, value in super().items():
            if key != '__dict__':  # Skip __dict__ attribute
                yield key, value


class BaseConfig(metaclass=ABCMeta):
    def __init__(self):
        super().__init__()
        self.model = AttrDict({'backbone': None, 'neck': None, 'head': None})

    def read_structure(self, path):
        with open(path, 'r') as f:
            structure = f.read()
        return structure


def get_config_by_file(config_file):
    try:
        sys.path.append(os.path.dirname(config_file))
        current_config = importlib.import_module(
            os.path.basename(config_file).split('.')[0])
        exp = current_config.Config()
    except Exception:
        raise ImportError(
            "{} doesn't contains class named 'Config'".format(config_file))
    return exp


def parse_config(config_file):
    """
    get config object by file.
    Args:
        config_file (str): file path of config.
    """
    assert (config_file is not None), 'plz provide config file'
    if config_file is not None:
        return get_config_by_file(config_file)
