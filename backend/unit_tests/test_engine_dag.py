import pytest
from app.engine.dag_builder import DAGBuilder
from app.utils.errors import BadRequestException


class TestDAGBuilder:
    def test_build_simple_dag(self):
        flow = {
            "nodes": [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "output", "position": {"x": 200, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b", "sourceHandle": None, "targetHandle": None},
            ],
        }
        dag = DAGBuilder(flow)
        assert "a" in dag.nodes
        assert "b" in dag.nodes
        assert len(dag.edges) == 1

    def test_topological_sort_linear(self):
        flow = {
            "nodes": [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "prompt", "position": {"x": 200, "y": 0}, "data": {}},
                {"id": "c", "type": "output", "position": {"x": 400, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b", "sourceHandle": None, "targetHandle": None},
                {"id": "e2", "source": "b", "target": "c", "sourceHandle": None, "targetHandle": None},
            ],
        }
        dag = DAGBuilder(flow)
        order = dag.topological_sort()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_topological_sort_independent_nodes(self):
        flow = {
            "nodes": [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "input", "position": {"x": 0, "y": 200}, "data": {}},
            ],
            "edges": [],
        }
        dag = DAGBuilder(flow)
        order = dag.topological_sort()
        assert len(order) == 2

    def test_detect_cycle(self):
        flow = {
            "nodes": [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "output", "position": {"x": 200, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b", "sourceHandle": None, "targetHandle": None},
                {"id": "e2", "source": "b", "target": "a", "sourceHandle": None, "targetHandle": None},
            ],
        }
        dag = DAGBuilder(flow)
        assert dag.detect_cycles() is True

    def test_no_cycle(self):
        flow = {
            "nodes": [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "output", "position": {"x": 200, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b", "sourceHandle": None, "targetHandle": None},
            ],
        }
        dag = DAGBuilder(flow)
        assert dag.detect_cycles() is False

    def test_validate_empty_nodes_raises(self):
        flow = {"nodes": [], "edges": []}
        dag = DAGBuilder(flow)
        with pytest.raises(BadRequestException):
            dag.validate()

    def test_validate_cycle_raises(self):
        flow = {
            "nodes": [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "output", "position": {"x": 200, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b", "sourceHandle": None, "targetHandle": None},
                {"id": "e2", "source": "b", "target": "a", "sourceHandle": None, "targetHandle": None},
            ],
        }
        dag = DAGBuilder(flow)
        with pytest.raises(BadRequestException):
            dag.validate()

    def test_validate_unknown_edge_source_raises(self):
        flow = {
            "nodes": [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "nonexistent", "target": "a", "sourceHandle": None, "targetHandle": None},
            ],
        }
        dag = DAGBuilder(flow)
        with pytest.raises(BadRequestException):
            dag.validate()

    def test_get_parents(self):
        flow = {
            "nodes": [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "output", "position": {"x": 200, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b", "sourceHandle": None, "targetHandle": None},
            ],
        }
        dag = DAGBuilder(flow)
        assert dag.get_parents("b") == ["a"]
        assert dag.get_parents("a") == []

    def test_get_children(self):
        flow = {
            "nodes": [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "output", "position": {"x": 200, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b", "sourceHandle": None, "targetHandle": None},
            ],
        }
        dag = DAGBuilder(flow)
        assert dag.get_children("a") == ["b"]
        assert dag.get_children("b") == []
