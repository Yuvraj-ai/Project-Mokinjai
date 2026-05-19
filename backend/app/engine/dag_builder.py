from collections import defaultdict, deque
from app.utils.errors import BadRequestException


class DAGBuilder:
    """Converts a flow definition (nodes + edges) into a directed acyclic graph
    and provides topological sorting."""

    def __init__(self, flow_definition: dict):
        self.nodes = {n["id"]: n for n in flow_definition.get("nodes", [])}
        self.edges = flow_definition.get("edges", [])
        self.adjacency: dict[str, list[str]] = defaultdict(list)
        self.reverse_adjacency: dict[str, list[str]] = defaultdict(list)
        self.in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}

        self._build()

    def _build(self):
        for edge in self.edges:
            src = edge["source"]
            tgt = edge["target"]
            self.adjacency[src].append(tgt)
            self.reverse_adjacency[tgt].append(src)
            self.in_degree[tgt] = self.in_degree.get(tgt, 0) + 1

    def detect_cycles(self) -> bool:
        """Returns True if the graph contains a cycle."""
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            for neighbor in self.adjacency.get(node_id, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node_id)
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        return False

    def topological_sort(self) -> list[str]:
        """Kahn's algorithm for topological sorting.
        Raises BadRequestException if cycle detected."""
        in_degree = dict(self.in_degree)
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        sorted_nodes = []

        while queue:
            node_id = queue.popleft()
            sorted_nodes.append(node_id)
            for neighbor in self.adjacency.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_nodes) != len(self.nodes):
            raise BadRequestException("Workflow contains a cycle")

        return sorted_nodes

    def get_parents(self, node_id: str) -> list[str]:
        """Get all parent node IDs for a given node."""
        return self.reverse_adjacency.get(node_id, [])

    def get_children(self, node_id: str) -> list[str]:
        """Get all child node IDs for a given node."""
        return self.adjacency.get(node_id, [])

    def validate(self):
        """Validate the flow definition."""
        if not self.nodes:
            raise BadRequestException("Workflow has no nodes")

        if self.detect_cycles():
            raise BadRequestException("Workflow contains a cycle")

        # Check all edge references exist
        for edge in self.edges:
            if edge["source"] not in self.nodes:
                raise BadRequestException(f"Edge references unknown source node: {edge['source']}")
            if edge["target"] not in self.nodes:
                raise BadRequestException(f"Edge references unknown target node: {edge['target']}")
