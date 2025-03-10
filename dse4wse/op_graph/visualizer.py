
import networkx as nx
import matplotlib.pyplot as plt

from dse4wse.op_graph.graph import OpGraph

def visualize_op_graph(op_graph: OpGraph):
    for node in op_graph.nodes():
        op_graph.nodes[node]['_vis_depth'] = 0

    for node in nx.topological_sort(op_graph):
        max_vis_depth = max([op_graph.nodes[pred]['_vis_depth']
            for pred in op_graph.predecessors(node)
        ], default=0) + 1
        op_graph.nodes[node]['_vis_depth'] = max_vis_depth

    for node in op_graph.nodes():
        original_depth = op_graph.nodes[node]['_vis_depth']
        op_graph.nodes[node]['_vis_depth'] = min([op_graph.nodes[succ]['_vis_depth']
            for succ in op_graph.successors(node)], default=original_depth) - 1

    pos = nx.multipartite_layout(op_graph, '_vis_depth', align='horizontal', scale=3)
    
    plt.figure(figsize=(20, 20))
    nx.draw_networkx(op_graph, pos=pos, node_size=5, font_size=2, arrowsize=5, width=0.5)

    plt.savefig('test.pdf')
    plt.clf()