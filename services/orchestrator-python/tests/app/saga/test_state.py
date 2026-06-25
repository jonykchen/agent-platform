"""Saga 状态定义测试"""

import time

import pytest

from app.saga.state import SagaState, SagaStatus, SagaStep


class TestSagaStatus:
    """SagaStatus 枚举测试"""

    def test_should_be_terminal_when_completed(self):
        """completed 应该是终态"""
        assert SagaStatus.COMPLETED.is_terminal() is True

    def test_should_be_terminal_when_failed(self):
        """failed 应该是终态"""
        assert SagaStatus.FAILED.is_terminal() is True

    def test_should_be_terminal_when_compensation_failed(self):
        """compensation_failed 应该是终态"""
        assert SagaStatus.COMPENSATION_FAILED.is_terminal() is True

    def test_should_not_be_terminal_when_running(self):
        """running 不应该是终态"""
        assert SagaStatus.RUNNING.is_terminal() is False

    def test_should_not_be_terminal_when_compensating(self):
        """compensating 不应该是终态"""
        assert SagaStatus.COMPENSATING.is_terminal() is False

    def test_should_transition_from_running_to_compensating(self):
        """running 应该可以转换到 compensating"""
        assert SagaStatus.RUNNING.can_transition_to(SagaStatus.COMPENSATING) is True

    def test_should_transition_from_running_to_completed(self):
        """running 应该可以转换到 completed"""
        assert SagaStatus.RUNNING.can_transition_to(SagaStatus.COMPLETED) is True

    def test_should_transition_from_running_to_failed(self):
        """running 应该可以转换到 failed"""
        assert SagaStatus.RUNNING.can_transition_to(SagaStatus.FAILED) is True

    def test_should_not_transition_from_running_to_running(self):
        """running 不应该可以转换到 running"""
        assert SagaStatus.RUNNING.can_transition_to(SagaStatus.RUNNING) is False

    def test_should_transition_from_compensating_to_completed(self):
        """compensating 应该可以转换到 completed"""
        assert SagaStatus.COMPENSATING.can_transition_to(SagaStatus.COMPLETED) is True

    def test_should_transition_from_compensating_to_compensation_failed(self):
        """compensating 应该可以转换到 compensation_failed"""
        assert SagaStatus.COMPENSATING.can_transition_to(SagaStatus.COMPENSATION_FAILED) is True

    def test_should_not_transition_from_completed(self):
        """completed 不应该可以转换到任何状态"""
        for status in SagaStatus:
            assert SagaStatus.COMPLETED.can_transition_to(status) is False

    def test_should_not_transition_from_failed(self):
        """failed 不应该可以转换到任何状态"""
        for status in SagaStatus:
            assert SagaStatus.FAILED.can_transition_to(status) is False


class TestSagaStep:
    """SagaStep 数据类测试"""

    def test_should_create_step_with_default_values(self):
        """应该使用默认值创建步骤"""
        step = SagaStep(step_index=0, tool_name="test_tool", status="pending")

        assert step.step_index == 0
        assert step.tool_name == "test_tool"
        assert step.status == "pending"
        assert step.input_data == {}
        assert step.output_data == {}
        assert step.error is None
        assert step.started_at is None
        assert step.completed_at is None
        assert step.compensation_status is None
        assert step.compensation_error is None

    def test_should_be_completed_when_status_is_completed(self):
        """status 为 completed 时应该返回 True"""
        step = SagaStep(step_index=0, tool_name="test", status="completed")
        assert step.is_completed() is True

    def test_should_not_be_completed_when_status_is_pending(self):
        """status 为 pending 时应该返回 False"""
        step = SagaStep(step_index=0, tool_name="test", status="pending")
        assert step.is_completed() is False

    def test_should_be_failed_when_status_is_failed(self):
        """status 为 failed 时应该返回 True"""
        step = SagaStep(step_index=0, tool_name="test", status="failed")
        assert step.is_failed() is True

    def test_should_need_compensation_when_completed_and_no_compensation(self):
        """已完成且未补偿时应该需要补偿"""
        step = SagaStep(step_index=0, tool_name="test", status="completed")
        assert step.needs_compensation() is True

    def test_should_not_need_compensation_when_not_completed(self):
        """未完成时不应该需要补偿"""
        step = SagaStep(step_index=0, tool_name="test", status="pending")
        assert step.needs_compensation() is False

    def test_should_not_need_compensation_when_already_compensated(self):
        """已补偿时不应该需要补偿"""
        step = SagaStep(
            step_index=0,
            tool_name="test",
            status="completed",
            compensation_status="compensated",
        )
        assert step.needs_compensation() is False

    def test_should_mark_compensating(self):
        """应该正确标记为补偿中"""
        step = SagaStep(step_index=0, tool_name="test", status="completed")
        step.mark_compensating()
        assert step.compensation_status == "compensating"

    def test_should_mark_compensated(self):
        """应该正确标记为已补偿"""
        step = SagaStep(step_index=0, tool_name="test", status="completed")
        step.mark_compensated()
        assert step.compensation_status == "compensated"

    def test_should_mark_compensation_failed(self):
        """应该正确标记补偿失败"""
        step = SagaStep(step_index=0, tool_name="test", status="completed")
        step.mark_compensation_failed("Network error")
        assert step.compensation_status == "failed"
        assert step.compensation_error == "Network error"


class TestSagaState:
    """SagaState 数据类测试"""

    def _create_saga_state(self) -> SagaState:
        """创建测试用 Saga 状态"""
        return SagaState(
            saga_id="saga-123",
            run_id="run-456",
            status=SagaStatus.RUNNING,
            created_at=time.time(),
        )

    def test_should_create_saga_state(self):
        """应该正确创建 Saga 状态"""
        state = self._create_saga_state()

        assert state.saga_id == "saga-123"
        assert state.run_id == "run-456"
        assert state.status == SagaStatus.RUNNING
        assert state.steps == []
        assert state.current_step_index == 0
        assert state.error is None

    def test_should_add_step(self):
        """应该正确添加步骤"""
        state = self._create_saga_state()

        step = state.add_step("tool_a", {"key": "value"})

        assert len(state.steps) == 1
        assert step.step_index == 0
        assert step.tool_name == "tool_a"
        assert step.input_data == {"key": "value"}
        assert step.status == "pending"
        assert state.current_step_index == 0

    def test_should_add_multiple_steps(self):
        """应该正确添加多个步骤"""
        state = self._create_saga_state()

        state.add_step("tool_a", {})
        state.add_step("tool_b", {})
        state.add_step("tool_c", {})

        assert len(state.steps) == 3
        assert state.current_step_index == 2

    def test_should_get_current_step(self):
        """应该正确获取当前步骤"""
        state = self._create_saga_state()
        state.add_step("tool_a", {})

        current = state.get_current_step()

        assert current is not None
        assert current.tool_name == "tool_a"

    def test_should_return_none_when_no_steps(self):
        """没有步骤时应该返回 None"""
        state = self._create_saga_state()

        assert state.get_current_step() is None

    def test_should_get_completed_steps(self):
        """应该正确获取已完成的步骤"""
        state = self._create_saga_state()
        step1 = state.add_step("tool_a", {})
        step2 = state.add_step("tool_b", {})
        step3 = state.add_step("tool_c", {})

        step1.status = "completed"
        step3.status = "completed"

        completed = state.get_completed_steps()

        assert len(completed) == 2
        assert step1 in completed
        assert step3 in completed

    def test_should_get_steps_needing_compensation_in_reverse_order(self):
        """应该按逆序获取需要补偿的步骤"""
        state = self._create_saga_state()
        step1 = state.add_step("tool_a", {})
        step2 = state.add_step("tool_b", {})
        step3 = state.add_step("tool_c", {})

        step1.status = "completed"
        step2.status = "completed"
        step3.status = "completed"

        needs_compensation = state.get_steps_needing_compensation()

        assert len(needs_compensation) == 3
        assert needs_compensation[0] == step3  # 逆序
        assert needs_compensation[1] == step2
        assert needs_compensation[2] == step1

    def test_should_transition_state(self):
        """应该正确转换状态"""
        state = self._create_saga_state()

        state.transition_to(SagaStatus.COMPLETED)

        assert state.status == SagaStatus.COMPLETED

    def test_should_raise_on_invalid_transition(self):
        """无效状态转换应该抛出异常"""
        state = self._create_saga_state()
        state.transition_to(SagaStatus.COMPLETED)

        with pytest.raises(ValueError, match="Invalid state transition"):
            state.transition_to(SagaStatus.RUNNING)

    def test_should_mark_failed(self):
        """应该正确标记失败"""
        state = self._create_saga_state()

        state.mark_failed("Connection timeout")

        assert state.status == SagaStatus.FAILED
        assert state.error == "Connection timeout"

    def test_should_mark_compensating(self):
        """应该正确标记补偿中"""
        state = self._create_saga_state()

        state.mark_compensating()

        assert state.status == SagaStatus.COMPENSATING

    def test_should_mark_completed(self):
        """应该正确标记完成"""
        state = self._create_saga_state()

        state.mark_completed()

        assert state.status == SagaStatus.COMPLETED

    def test_should_mark_compensation_failed(self):
        """应该正确标记补偿失败"""
        state = self._create_saga_state()

        state.mark_compensation_failed("Refund API error")

        assert state.status == SagaStatus.COMPENSATION_FAILED
        assert state.error == "Refund API error"

    def test_should_serialize_to_dict(self):
        """应该正确序列化为字典"""
        state = self._create_saga_state()
        state.add_step("tool_a", {"key": "value"})

        data = state.to_dict()

        assert data["saga_id"] == "saga-123"
        assert data["run_id"] == "run-456"
        assert data["status"] == "running"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["tool_name"] == "tool_a"

    def test_should_deserialize_from_dict(self):
        """应该正确从字典反序列化"""
        data = {
            "saga_id": "saga-123",
            "run_id": "run-456",
            "status": "running",
            "steps": [
                {
                    "step_index": 0,
                    "tool_name": "tool_a",
                    "status": "completed",
                    "input_data": {"key": "value"},
                    "output_data": {"result": "ok"},
                }
            ],
            "current_step_index": 0,
            "error": None,
            "metadata": {},
            "created_at": 1234567890.0,
            "updated_at": 1234567890.0,
        }

        state = SagaState.from_dict(data)

        assert state.saga_id == "saga-123"
        assert state.run_id == "run-456"
        assert state.status == SagaStatus.RUNNING
        assert len(state.steps) == 1
        assert state.steps[0].tool_name == "tool_a"
        assert state.steps[0].output_data == {"result": "ok"}

    def test_should_roundtrip_serialize_deserialize(self):
        """序列化和反序列化应该可以往返"""
        state = self._create_saga_state()
        state.add_step("tool_a", {"key": "value"})
        state.steps[0].status = "completed"
        state.steps[0].output_data = {"result": "ok"}

        data = state.to_dict()
        restored = SagaState.from_dict(data)

        assert restored.saga_id == state.saga_id
        assert restored.run_id == state.run_id
        assert restored.status == state.status
        assert len(restored.steps) == len(state.steps)
        assert restored.steps[0].tool_name == state.steps[0].tool_name
        assert restored.steps[0].output_data == state.steps[0].output_data
