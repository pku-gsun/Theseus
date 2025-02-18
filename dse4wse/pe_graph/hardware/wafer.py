
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, List
from itertools import product
import networkx as nx

from .reticle import Reticle
from .dram_port import DramPort
from .power_table import WsePowerTable

class WaferScaleEngine():

    def __init__(self,
                 reticle_array_height: int,
                 reticle_array_width: int,
                 inter_reticle_bandwidth: int,
                 dram_size: int,
                 dram_bandwidth: int,
                 dram_stacking_type: str,
                 reticle_config: Dict,
                 **kwargs,
                 ) -> None:
        
        self.reticle_array_height = reticle_array_height
        self.reticle_array_width = reticle_array_width
        self.inter_reticle_bandwidth = inter_reticle_bandwidth
        self.dram_size = dram_size
        self.dram_bandwidth = dram_bandwidth
        self.dram_stacking_type = dram_stacking_type
        self.reticle_config = reticle_config
        assert dram_stacking_type in ['2d', '3d']

        self._reticle_graph = self.__build_reticle_graph()

    @property
    def reticle_compute_power(self):
        return Reticle.get_compute_power(self.reticle_config)
    
    def get_bisection_bandwidth(self):
        """ This is actually the maximum bandwidth 2d-torus could offer, not the conventional bisection bandwidth
        """
        return 2 * (self.reticle_array_height + self.reticle_array_width) * self.inter_reticle_bandwidth
    
    def get_total_dram_bandwidth(self):
        if self.dram_stacking_type == '2d':
            num_dram_port = 2 * (self.reticle_array_height + self.reticle_array_width)
        elif self.dram_stacking_type == '3d':
            num_dram_port = self.reticle_array_height * self.reticle_array_width
        else:
            raise NotImplementedError
        return num_dram_port * self.dram_bandwidth
    
    def __build_reticle_graph(self):
        # build graph skeleton
        H, W = self.reticle_array_height, self.reticle_array_width
        G = nx.grid_2d_graph(range(-1, H + 1), range(-1, W + 1), create_using=nx.DiGraph)
        G : nx.DiGraph
        for node, ndata in G.nodes(data=True):
            ndata['reticle'] = None
            ndata['dram_port'] = None
        for node in [(-1, -1), (-1, W), (H, -1), (H, W)]:
            G.remove_node(node)

        def add_reticle(x, y, reticle: Reticle):
            G.nodes[(x, y)]['reticle'] = reticle

        def add_dram_port(x, y, dram_port: DramPort):
            G.nodes[(x, y)]['dram_port'] = dram_port

        # reticle arrays
        for x, y in product(range(H), range(W)):
            reticle = Reticle(coordinate=(x, y), **self.reticle_config)
            add_reticle(x, y, reticle)

        # dram ports
        if self.dram_stacking_type == '2d':
            for x in range(0, self.reticle_array_height):
                add_dram_port(x, -1, DramPort())
                add_dram_port(x, self.reticle_array_width, DramPort())
            for y in range(0, self.reticle_array_width):
                add_dram_port(-1, y, DramPort())
                add_dram_port(self.reticle_array_height, y, DramPort())
        elif self.dram_stacking_type == '3d':
            for x, y in product(range(self.reticle_array_height), range(self.reticle_array_width)):
                add_dram_port(x, y, DramPort())
        else:
            raise NotImplementedError

        return G
    
    def get_node_from_coordinate(self, x: int, y: int):
        return self.nodes([x, y])  # for direct graph operations
            
    def get_reticle_from_coordinate(self, x: int, y: int) -> Reticle:
        assert x >= 0 and x < self.reticle_array_height
        assert y >= 0 and y < self.reticle_array_width
        ret = self._reticle_graph.nodes[(x, y)]['reticle']
        assert ret
        return ret
    
    def get_dram_port_from_coordinate(self, x: int, y: int) -> DramPort:
        if self.dram_stacking_type == '2d':
            assert x in [-1, self.reticle_array_height] or y in [-1, self.reticle_array_width]
            ret = self._reticle_graph.nodes[(x, y)]['dram_port']
        elif self.dram_stacking_type == '3d':
            assert x in range(self.reticle_array_height) and y in range(self.reticle_array_width)
            ret = self._reticle_graph.nodes[(x, y)]['dram_port']
        else:
            raise RuntimeError
        assert ret
        return ret

    def buiid_power_table(self) -> WsePowerTable:
        """Translate parameters into raw design parameters, and build a power table
        """
        reticle_config = self.reticle_config
        core_config = reticle_config['core_config']
        WSE_FREQUENCY = 1e9

        wse_power_table = WsePowerTable(
            core_buffer_size=int(core_config['core_sram_size'] / 1e3),
            core_buffer_bw=int(core_config['core_buffer_bandwidth'] / WSE_FREQUENCY),
            core_mac_num=int(core_config['core_compute_power'] / WSE_FREQUENCY),
            core_noc_bw=int(reticle_config['inter_core_bandwidth'] * 8 / WSE_FREQUENCY),
            core_noc_vc=core_config['core_noc_vc'],
            core_noc_buffer_size=core_config['core_noc_buffer_size'],
            reticle_bw=1,  # doesn't matter ...
            core_array_h=reticle_config['core_array_height'],
            core_array_w=reticle_config['core_array_width'],
            wafer_mem_bw=int(self.dram_bandwidth / WSE_FREQUENCY),
            reticle_array_h=self.reticle_array_height,
            reticle_array_w=self.reticle_array_width,
            package_type='cerebras',  # default to be cerebras, for now
        )

        return wse_power_table