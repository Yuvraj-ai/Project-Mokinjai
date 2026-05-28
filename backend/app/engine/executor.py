import time
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.logging import logger
from app.models.workflow import Workflow
from app.models.execution import Execution
from app.engine.dag_builder import DAGBuilder
from app.engine.context import ExecutionContext
from app.engine.modules.registry import ModuleRegistry


class WorkflowExecutor:
    """Main workflow execution engine.

    1. Loads workflow definition
    2. Builds DAG and topological sort
    3. Executes nodes in order, passing data through context
    4. Handles conditional branching
    5. Records execution trace
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, execution_id: str) -> Execution:
        logger.info(f"Starting execution {execution_id}")

        result = await self.db.execute(
            select(Execution).where(Execution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if execution is None:
            logger.error(f"Execution {execution_id} not found")
            raise ValueError(f"Execution {execution_id} not found")

        result = await self.db.execute(
            select(Workflow).where(Workflow.id == execution.workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            logger.error(f"Workflow {execution.workflow_id} not found for execution {execution_id}")
            execution.status = "failed"
            execution.error_message = "Workflow not found"
            await self.db.commit()
            return execution

        execution.status = "running"
        execution.started_at = datetime.now(timezone.utc)
        await self.db.commit()
        logger.info(f"Execution {execution_id} running — workflow '{workflow.name}' v{workflow.version}")

        start_time = time.time()

        try:
            flow_def = workflow.flow_definition
            dag = DAGBuilder(flow_def)
            dag.validate()

            sorted_nodes = dag.topological_sort()
            logger.debug(f"DAG built: {len(sorted_nodes)} nodes to execute")

            context = ExecutionContext(execution.input_data)

            for node_id in sorted_nodes:
                if context.is_skipped(node_id):
                    context.add_trace_entry(node_id, "skipped", "skipped")
                    continue

                node = dag.nodes[node_id]
                node_type = node["type"]
                node_config = node.get("data", {})

                module = ModuleRegistry.get_module(node_type)
                parent_ids = dag.get_parents(node_id)
                inputs = context.get_inputs_for(node_id, parent_ids)

                node_start = time.time()
                try:
                    output = await module.execute(node_config, inputs, context)
                    node_duration = int((time.time() - node_start) * 1000)

                    context.set_output(node_id, output)
                    context.add_trace_entry(
                        node_id, node_type, "completed",
                        inputs=inputs, outputs=output, duration_ms=node_duration,
                    )
                    logger.debug(f"Node {node_id} ({node_type}) completed in {node_duration}ms")

                    if node_type == "conditional" and "branch" in output:
                        self._handle_branching(dag, node_id, output["branch"], context)
                        logger.debug(f"Conditional {node_id}: branch={output['branch']}")

                except Exception as e:
                    node_duration = int((time.time() - node_start) * 1000)
                    context.add_trace_entry(
                        node_id, node_type, "failed",
                        inputs=inputs, error=str(e), duration_ms=node_duration,
                    )
                    logger.error(f"Node {node_id} ({node_type}) failed after {node_duration}ms: {e}")
                    raise

            total_time = int((time.time() - start_time) * 1000)
            execution.status = "completed"
            execution.output_data = context.get_final_output()
            execution.execution_trace = {"nodes": context.trace}
            execution.execution_time_ms = total_time
            execution.token_usage = context.total_token_usage
            execution.completed_at = datetime.now(timezone.utc)
            logger.info(f"Execution {execution_id} completed in {total_time}ms")

        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            execution.status = "failed"
            execution.error_message = str(e)
            execution.execution_trace = {"nodes": context.trace} if 'context' in dir() else None
            execution.execution_time_ms = total_time
            execution.completed_at = datetime.now(timezone.utc)
            logger.error(f"Execution {execution_id} failed after {total_time}ms: {e}")

        await self.db.commit()
        await self.db.refresh(execution)
        return execution

    def _handle_branching(
        self, dag: DAGBuilder, node_id: str, branch: str, context: ExecutionContext
    ):
        children = dag.get_children(node_id)

        for i, child_id in enumerate(children):
            for edge in dag.edges:
                if edge["source"] == node_id and edge["target"] == child_id:
                    handle = edge.get("sourceHandle", "")
                    if handle == "true" and branch != "true":
                        self._skip_subtree(dag, child_id, context)
                    elif handle == "false" and branch != "false":
                        self._skip_subtree(dag, child_id, context)
                    break

    def _skip_subtree(self, dag: DAGBuilder, node_id: str, context: ExecutionContext):
        context.skip_node(node_id)
        for child_id in dag.get_children(node_id):
            parents = dag.get_parents(child_id)
            if all(context.is_skipped(p) for p in parents):
                self._skip_subtree(dag, child_id, context)
