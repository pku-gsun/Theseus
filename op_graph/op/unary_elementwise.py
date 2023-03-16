import os
import sys
from typing import Dict, List
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from base import Operator
from utils import (
    ArchConfig, SbpSignature, TensorInfo, generate_split_from_fixed_shape
)


class UnaryElementwiseOperator(Operator):
    def __init__(self, name: str, op_type: str, input_tensors: Dict[str, TensorInfo], output_tensors: Dict[str, TensorInfo], 
                 operation_intensity=1, *args, **kwargs) -> None:
        super().__init__(name, op_type, input_tensors, output_tensors, *args, **kwargs)
        self.operation_intensity = operation_intensity  # operation / element
        assert len(input_tensors) == 1, input_tensors
        assert len(output_tensors) == 1, output_tensors
        assert "in" in input_tensors
        assert "out" in output_tensors

    def _estimate_compute_cost(self, sbp_signatures: Dict[str, SbpSignature], arch_config: ArchConfig) -> float:
        tensor_info = self.input_tensors['in']
        sbp_signature = sbp_signatures['in']
        input_numel = tensor_info.numel() // sbp_signature.get_total_cores()
        total_operation = input_numel * self.operation_intensity

        compute_power = arch_config.get_compute_power()  # operation/cycle
        memory_bandwidth = arch_config.get_memory_bandwidth() // tensor_info.dtype_size()  # element/cycle
        maximum_intensity = compute_power / memory_bandwidth  # operation/element

        if self.operation_intensity < maximum_intensity:
            actual_intensity = memory_bandwidth * self.operation_intensity
        else:
            actual_intensity = compute_power
        total_cycles = total_operation / actual_intensity
        return total_cycles
    
    def _estimate_memory_cost(self, sbp_signatures: Dict[str, SbpSignature], arch_config: ArchConfig):
        tensor_info = self.input_tensors['in']
        sbp_signature = sbp_signatures['in']
        used_memory = tensor_info.numel() * sbp_signature.get_broadcast_size() * tensor_info.dtype_size() * 3 # input + output + grad
        actual_memory = arch_config.get_memory_size()

        return 0 if used_memory < actual_memory else np.inf
    
    def _generate_candidate_sbp_signature(self):
        tensor_info = self.input_tensors['in']
        num_dims = len(tensor_info.shape)
        split_1d = generate_split_from_fixed_shape(
            tensor_shape=self.input_tensors['in'].shape,
            split_dims=[num_dims - 1],
            core_range=self.num_core_range,
        )
        split_2d = generate_split_from_fixed_shape(
            tensor_shape=self.input_tensors['in'].shape,
            split_dims=[num_dims - 2, num_dims - 1],
            core_range=self.num_core_range,
        )
        self._candidate_sbp_signatures = split_1d + split_2d
    
    @property
    def _rule_table(self) -> pd.DataFrame:
        tensor_info = self.input_tensors['in']
        num_dims = len(tensor_info.shape)
        data = {
            'in': ['B'] + [f"S({i})" for i in range(num_dims)],
            'out': ['B'] + [f"S({i})" for i in range(num_dims)],
        }
        return pd.DataFrame(data)