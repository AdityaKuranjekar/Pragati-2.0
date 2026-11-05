import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, afterEach } from "vitest";
import { BottleneckPanel, GroupTable, Heatmap } from "@/components/prototype/teacher";
import { ConceptCard, LearnerPanel, NextStepCard, PracticePanel, LearnerScreen, LearnerIndex, primaryAction } from "@/components/prototype/learner";
import { ErrorState, Loading } from "@/components/prototype/common";
import { ProtoError } from "@/lib/prototype/client";
import { BAND_LABEL } from "@/lib/prototype/labels";
import { BANDS } from "@/lib/prototype/schemas";
import { A, F, R, bottlenecks, config, nextStep, state, states, stubFetch } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("band labels are printed as text", () => {
  it.each(BANDS)("concept card prints the %s label", (band) => {
    render(<ConceptCard c={{ concept_id: R, band, p_known: 0.5, uncertainty: 0.3, evidence_count: 4 }} />);
    expect(screen.getByText(BAND_LABEL[band])).toBeInTheDocument();
  });
  it("heatmap cells print a label for every band, with the answer count", () => {
    render(<Heatmap config={config} states={states} />);
    const t = within(screen.getByTestId("heatmap"));
    for (const label of ["Mastered", "Uncertain", "Not mastered", "Insufficient evidence"]) expect(t.getAllByText(label).length).toBeGreaterThan(0);
    expect(screen.getByTestId("cell-demo-a-roots_nature")).toHaveTextContent("Not mastered");
    expect(screen.getByTestId("cell-demo-a-roots_nature")).toHaveTextContent("3 answers");
    expect(screen.getByTestId("cell-demo-a-equation_formation")).toHaveTextContent("Insufficient evidence");
    expect(screen.getByTestId("cell-demo-a-equation_formation")).toHaveTextContent("0 answers");
  });
  it("a learner whose state failed shows Unavailable, not a guess", () => {
    render(<Heatmap config={config} states={{ ...states, "sim-02": new ProtoError("denied", "no", 403) }} />);
    expect(screen.getAllByText("Unavailable").length).toBe(3);
  });
  it("group view counts learners per band as text", () => {
    render(<GroupTable config={config} states={states} />);
    expect(screen.getByRole("columnheader", { name: "Insufficient evidence" })).toBeInTheDocument();
  });
  it("low evidence shows 'early estimate', enough evidence shows a range", () => {
    const { unmount } = render(<ConceptCard c={{ concept_id: F, band: "insufficient", p_known: 0.1, uncertainty: 1, evidence_count: 0 }} />);
    expect(screen.getByText("early estimate")).toBeInTheDocument();
    expect(screen.queryByText(/0\.10/)).toBeNull();
    unmount();
    render(<ConceptCard c={{ concept_id: R, band: "unmastered", p_known: 0.2303, uncertainty: 0.5, evidence_count: 3 }} />);
    expect(screen.getByText("0.23 ± 0.50")).toBeInTheDocument();
    expect(screen.getByText("3 answers")).toBeInTheDocument();
  });
});

describe("unreviewed edges", () => {
  it("proposed edges carry the warning words and the warning style hook", () => {
    render(<BottleneckPanel data={bottlenecks("proposed")} />);
    const edges = screen.getAllByTestId("edge");
    expect(edges).toHaveLength(2);
    for (const e of edges) {
      expect(e).toHaveAttribute("data-review", "proposed");
      expect(within(e).getByText("proposed, not yet reviewed")).toBeInTheDocument();
    }
  });
  it("a reviewed edge is not marked as proposed", () => {
    render(<BottleneckPanel data={bottlenecks("reviewed")} />);
    expect(screen.queryByText("proposed, not yet reviewed")).toBeNull();
    expect(screen.getAllByText("Review state: reviewed")).toHaveLength(2);
  });
  it("shows the learners-blocked count as returned", () => {
    render(<BottleneckPanel data={bottlenecks()} />);
    expect(screen.getAllByTestId("bottleneck-row")[0]).toHaveTextContent("3 of 4 learners blocked");
  });
});

describe("empty states", () => {
  it("no bottleneck", () => {
    render(<BottleneckPanel data={{ ...bottlenecks(), bottlenecks: [] }} />);
    expect(screen.getByText("No bottleneck on current evidence")).toBeInTheDocument();
  });
  it("practice: the bank is not approved, in plain words, with no placeholder question", () => {
    render(<PracticePanel step={nextStep()} mode="learner" />);
    expect(screen.getByText("No practice item is available")).toBeInTheDocument();
    expect(screen.getByText(/no approved items yet/)).toBeInTheDocument();
    expect(screen.getByTestId("practice-api-reason")).toHaveTextContent("No unanswered approved items for this concept.");
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByText(/\?$/)).toBeNull();
  });
  it("practice: no item for another reason", () => {
    render(<PracticePanel step={nextStep({ selection: null, concept_id: null, reason: "Goal mastered on current evidence; no recheck is due." })} mode="learner" />);
    expect(screen.getByText("Nothing to practise right now")).toBeInTheDocument();
  });
  it("learner index with no demo learner", async () => {
    const { fn } = stubFetch({ "/api/proto/config": () => ({ body: { ...config, roster: config.roster.filter((r) => r.origin === "SIM") } }) });
    vi.stubGlobal("fetch", fn);
    render(<LearnerIndex />);
    expect(await screen.findByText("No demo learners")).toBeInTheDocument();
  });
});

describe("loading, error and permission-denied states", () => {
  it("loading", () => {
    render(<Loading what="the cohort" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading the cohort");
  });
  it("permission denied does not offer a retry and says nothing was changed", () => {
    render(<ErrorState error={new ProtoError("denied", "teacher is not assigned to this cohort", 403)} onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Permission denied");
    expect(screen.getByRole("alert")).toHaveTextContent("teacher is not assigned to this cohort");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
  it("service error offers a retry", () => {
    render(<ErrorState error={new ProtoError("unavailable", "The service could not be reached.")} onRetry={() => {}} />);
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
  it("the learner screen shows denied for a non-demo learner", async () => {
    const { fn } = stubFetch({ "/api/proto/config": () => ({ body: config }) });
    vi.stubGlobal("fetch", fn);
    render(<LearnerScreen learnerId="sim-01" />);
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
  it("a 403 from the API becomes the denied state", async () => {
    const { fn } = stubFetch({
      "/learners/demo-a/state": () => ({ status: 403, body: { detail: "students may reach only their own learner" } }),
      "/learners/demo-a/next-step": () => ({ body: nextStep() }),
    });
    vi.stubGlobal("fetch", fn);
    render(<LearnerPanel learnerId="demo-a" principal="demo-b" mode="learner" origin="DEMO FIXTURE" />);
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
  it("a response in the wrong shape is reported, not displayed", async () => {
    const { fn } = stubFetch({ "/learners/demo-a/state": () => ({ body: { nope: 1 } }), "/learners/demo-a/next-step": () => ({ body: nextStep() }) });
    vi.stubGlobal("fetch", fn);
    render(<LearnerPanel learnerId="demo-a" principal="demo-a" mode="learner" origin="DEMO FIXTURE" />);
    expect(await screen.findByText("Unexpected response")).toBeInTheDocument();
  });
});

describe("next-step display", () => {
  it("shows the action, the reason exactly as returned, the evidence and the policy version", () => {
    const step = nextStep();
    render(<NextStepCard step={step} origin="DEMO FIXTURE" />);
    expect(screen.getByTestId("primary-action")).toHaveTextContent("Review prerequisite: Nature of roots and discriminant");
    expect(screen.getByTestId("reason").textContent).toBe(step.recommendation!.reason);
    expect(screen.getByTestId("item-status").textContent).toBe(step.reason);
    const ev = screen.getByTestId("evidence");
    expect(ev).toHaveTextContent("Algebra of complex numbers: 5 answers");
    expect(ev).toHaveTextContent("Formation of quadratic equations: 0 answers");
    expect(screen.getByTestId("policy")).toHaveTextContent("policy-v0.1");
    expect(screen.getByText("[DEMO FIXTURE]")).toBeInTheDocument();
  });
  it("one primary action per step kind", () => {
    expect(primaryAction(nextStep({ kind: "recheck", concept_id: A }))).toBe("Recheck: Algebra of complex numbers");
    expect(primaryAction(nextStep({ recommendation: { ...nextStep().recommendation!, action: "goal_mastered", concept_id: null }, concept_id: null }))).toBe("Goal mastered on current evidence");
  });
});

describe("no attempt control for a teacher", () => {
  const withItem = nextStep({ kind: "practice", item_id: "roots_nature-easy-0", demo_unapproved_allowed: true, selection: { trace: { approved_in_pool: 4 } } });
  it("PracticePanel in teacher mode renders no button, even when an item is served", () => {
    render(<PracticePanel step={withItem} mode="teacher" />);
    expect(screen.getByTestId("item-id")).toHaveTextContent("roots_nature-easy-0");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryByText(/Record as/)).toBeNull();
  });
  it("LearnerPanel in teacher mode renders no button and never posts", async () => {
    const { fn, calls } = stubFetch({
      "/learners/demo-a/state": () => ({ body: states["demo-a"] }),
      "/learners/demo-a/next-step": () => ({ body: withItem }),
    });
    vi.stubGlobal("fetch", fn);
    render(<LearnerPanel learnerId="demo-a" principal="teacher" mode="teacher" origin="DEMO FIXTURE" />);
    await screen.findByTestId("item-id");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(calls.every((c) => c.method === "GET")).toBe(true);
    expect(calls.some((c) => c.url.includes("/as/teacher/"))).toBe(true);
  });
  it("the learner sees the control only when the API served an item under the demo flag", () => {
    const { unmount } = render(<PracticePanel step={withItem} mode="learner" />);
    expect(screen.getByRole("button", { name: "Record as correct" })).toBeInTheDocument();
    unmount();
    render(<PracticePanel step={{ ...withItem, demo_unapproved_allowed: false }} mode="learner" />);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });
});

describe("practice submit re-reads the state from the API", () => {
  it("posts one attempt, then fetches state and next-step again, and shows what the API returns", async () => {
    let answered = false;
    const item = nextStep({ kind: "practice", item_id: "roots_nature-easy-0", demo_unapproved_allowed: true, selection: { trace: { approved_in_pool: 4 } } });
    const { fn, calls } = stubFetch({
      "/learners/demo-a/state": () => ({ body: answered ? state("demo-a", [[A, "mastered", 0.997, 5], [R, "unmastered", 0.3, 4], [F, "insufficient", 0.1, 0]]) : states["demo-a"] }),
      "/learners/demo-a/next-step": () => ({ body: item }),
      "/learners/demo-a/events": (init) => { answered = true; expect(JSON.parse(String(init?.body))).toMatchObject({ concept_id: R, item_id: "roots_nature-easy-0", correct: true }); return { status: 201, body: { event_id: "x", seq: 8, duplicate: false } }; },
    });
    vi.stubGlobal("fetch", fn);
    render(<LearnerPanel learnerId="demo-a" principal="demo-a" mode="learner" origin="DEMO FIXTURE" />);
    expect(await screen.findByText("3 answers")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Record as correct" }));
    expect(await screen.findByText("4 answers")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
    expect(calls.filter((c) => c.url.endsWith("/state"))).toHaveLength(2);
    expect(calls.filter((c) => c.url.endsWith("/next-step"))).toHaveLength(2);
  });
  it("a refusal is shown in the API's words and the state is not changed", async () => {
    const item = nextStep({ kind: "practice", item_id: "roots_nature-easy-0", demo_unapproved_allowed: true, selection: { trace: { approved_in_pool: 4 } } });
    const { fn } = stubFetch({
      "/learners/demo-a/state": () => ({ body: states["demo-a"] }),
      "/learners/demo-a/next-step": () => ({ body: item }),
      "/learners/demo-a/events": () => ({ status: 422, body: { detail: "item was not served to this learner" } }),
    });
    vi.stubGlobal("fetch", fn);
    render(<LearnerPanel learnerId="demo-a" principal="demo-a" mode="learner" origin="DEMO FIXTURE" />);
    await userEvent.click(await screen.findByRole("button", { name: "Record as incorrect" }));
    await waitFor(() => expect(screen.getByTestId("refusal")).toHaveTextContent("item was not served to this learner"));
    expect(screen.getByText("3 answers")).toBeInTheDocument();
  });
});
