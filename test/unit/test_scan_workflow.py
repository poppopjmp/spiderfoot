"""Tests for spiderfoot.scan_workflow."""

import pytest
from spiderfoot.scan_workflow import (
    StepType,
    StepStatus,
    StepResult,
    WorkflowStep,
    ModuleStep,
    SequenceStep,
    ParallelStep,
    ConditionalStep,
    DelayStep,
    CheckpointStep,
    ScanWorkflow,
)


class TestStepResult:
    def test_defaults(self):
        r = StepResult(step_name="s1")
        assert r.step_name == "s1"
        assert r.status == StepStatus.PENDING

    def test_to_dict(self):
        r = StepResult(step_name="s1", status=StepStatus.COMPLETED, elapsed_ms=5.0)
        d = r.to_dict()
        assert d["step_name"] == "s1"
        assert d["status"] == "completed"


class TestWorkflowStep:
    def test_defaults(self):
        s = WorkflowStep("step1")
        assert s.name == "step1"
        assert s.status == StepStatus.PENDING

    def test_execute(self):
        s = WorkflowStep("step1")
        r = s.execute({})
        assert r.status == StepStatus.COMPLETED
        assert s.status == StepStatus.COMPLETED

    def test_reset(self):
        s = WorkflowStep("step1")
        s.execute({})
        s.reset()
        assert s.status == StepStatus.PENDING
        assert s.result is None

    def test_to_dict(self):
        s = WorkflowStep("step1", tags=["foo"])
        d = s.to_dict()
        assert d["name"] == "step1"
        assert d["tags"] == ["foo"]


class TestModuleStep:
    def test_execute(self):
        s = ModuleStep("s1", module_name="sfp_dns", options={"dns_server": "8.8.8.8"})
        r = s.execute({})
        assert r.status == StepStatus.COMPLETED
        assert r.output["module"] == "sfp_dns"

    def test_to_dict(self):
        s = ModuleStep("s1", module_name="sfp_dns")
        d = s.to_dict()
        assert d["module_name"] == "sfp_dns"
        assert d["type"] == "module"


class TestSequenceStep:
    def test_execute_all(self):
        seq = SequenceStep("seq")
        seq.add_step(WorkflowStep("a"))
        seq.add_step(WorkflowStep("b"))
        r = seq.execute({})
        assert r.status == StepStatus.COMPLETED
        assert len(r.output) == 2

    def test_chaining(self):
        seq = SequenceStep("seq")
        result = seq.add_step(WorkflowStep("a"))
        assert result is seq

    def test_reset(self):
        seq = SequenceStep("seq")
        seq.add_step(WorkflowStep("a"))
        seq.execute({})
        seq.reset()
        assert seq.status == StepStatus.PENDING
        assert seq.steps[0].status == StepStatus.PENDING

    def test_to_dict(self):
        seq = SequenceStep("seq")
        seq.add_step(WorkflowStep("a"))
        d = seq.to_dict()
        assert d["type"] == "sequence"
        assert len(d["steps"]) == 1


class TestParallelStep:
    def test_execute_all(self):
        par = ParallelStep("par")
        par.add_step(WorkflowStep("a"))
        par.add_step(WorkflowStep("b"))
        r = par.execute({})
        assert r.status == StepStatus.COMPLETED
        assert len(r.output) == 2

    def test_chaining(self):
        par = ParallelStep("par")
        result = par.add_step(WorkflowStep("a"))
        assert result is par

    def test_reset(self):
        par = ParallelStep("par")
        par.add_step(WorkflowStep("a"))
        par.execute({})
        par.reset()
        assert par.status == StepStatus.PENDING

    def test_to_dict(self):
        par = ParallelStep("par")
        par.add_step(WorkflowStep("a"))
        d = par.to_dict()
        assert d["type"] == "parallel"
        assert len(d["steps"]) == 1


class TestConditionalStep:
    def test_true_branch(self):
        step = ConditionalStep(
            "cond",
            condition=lambda ctx: ctx.get("flag", False),
            if_true=WorkflowStep("yes"),
            if_false=WorkflowStep("no"),
        )
        r = step.execute({"flag": True})
        assert r.status == StepStatus.COMPLETED
        assert r.output.step_name == "yes"

    def test_false_branch(self):
        step = ConditionalStep(
            "cond",
            condition=lambda ctx: ctx.get("flag", False),
            if_true=WorkflowStep("yes"),
            if_false=WorkflowStep("no"),
        )
        r = step.execute({"flag": False})
        assert r.output.step_name == "no"

    def test_no_branch(self):
        step = ConditionalStep(
            "cond",
            condition=lambda ctx: False,
        )
        r = step.execute({})
        assert r.status == StepStatus.COMPLETED
        assert r.output is None

    def test_condition_error(self):
        step = ConditionalStep(
            "cond",
            condition=lambda ctx: ctx["missing_key"],
            if_false=WorkflowStep("fallback"),
        )
        r = step.execute({})
        assert r.output.step_name == "fallback"

    def test_reset(self):
        step = ConditionalStep(
            "cond",
            condition=lambda ctx: True,
            if_true=WorkflowStep("yes"),
        )
        step.execute({})
        step.reset()
        assert step.status == StepStatus.PENDING

    def test_to_dict(self):
        step = ConditionalStep(
            "cond",
            condition=lambda ctx: True,
            if_true=WorkflowStep("yes"),
        )
        d = step.to_dict()
        assert d["type"] == "conditional"
        assert d["if_true"]["name"] == "yes"


class TestDelayStep:
    def test_execute(self):
        s = DelayStep("wait", delay_seconds=0.5)
        r = s.execute({})
        assert r.status == StepStatus.COMPLETED
        assert r.output["delay_seconds"] == 0.5

    def test_to_dict(self):
        s = DelayStep("wait", delay_seconds=2.0)
        d = s.to_dict()
        assert d["delay_seconds"] == 2.0


class TestCheckpointStep:
    def test_execute(self):
        s = CheckpointStep("cp1")
        r = s.execute({})
        assert r.status == StepStatus.COMPLETED
        assert r.output["checkpoint"] == "cp1"


class TestScanWorkflow:
    def test_empty_workflow(self):
        wf = ScanWorkflow("test_wf", description="test")
        r = wf.execute()
        assert r.status == StepStatus.COMPLETED
        assert wf.status == StepStatus.COMPLETED

    def test_add_and_execute(self):
        wf = ScanWorkflow("test_wf")
        wf.add_step(ModuleStep("s1", "sfp_dns"))
        wf.add_step(ModuleStep("s2", "sfp_whois"))
        r = wf.execute()
        assert r.status == StepStatus.COMPLETED
        assert len(wf.results) == 2

    def test_chaining(self):
        wf = ScanWorkflow("test_wf")
        result = wf.add_step(WorkflowStep("a"))
        assert result is wf

    def test_nested_workflow(self):
        wf = ScanWorkflow("test_wf")
        par = ParallelStep("par")
        par.add_step(ModuleStep("dns", "sfp_dns"))
        par.add_step(ModuleStep("whois", "sfp_whois"))
        wf.add_step(par)
        wf.add_step(ModuleStep("export", "sfp_export"))
        r = wf.execute()
        assert r.status == StepStatus.COMPLETED

    def test_reset(self):
        wf = ScanWorkflow("test_wf")
        wf.add_step(WorkflowStep("a"))
        wf.execute()
        wf.reset()
        assert wf.status == StepStatus.PENDING
        assert len(wf.results) == 0

    def test_to_dict(self):
        wf = ScanWorkflow("test_wf", description="desc")
        wf.add_step(WorkflowStep("a"))
        d = wf.to_dict()
        assert d["name"] == "test_wf"
        assert d["description"] == "desc"
        assert len(d["steps"]) == 1

    def test_steps_property(self):
        wf = ScanWorkflow("test_wf")
        wf.add_step(WorkflowStep("a"))
        wf.add_step(WorkflowStep("b"))
        assert len(wf.steps) == 2

    def test_with_conditional(self):
        wf = ScanWorkflow("test_wf")
        wf.add_step(ConditionalStep(
            "check",
            condition=lambda ctx: True,
            if_true=ModuleStep("deep_scan", "sfp_dns"),
        ))
        r = wf.execute()
        assert r.status == StepStatus.COMPLETED
