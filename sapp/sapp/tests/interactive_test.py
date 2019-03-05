#!/usr/bin/env python3

import sys
from datetime import datetime
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from sapp.db import DB
from sapp.interactive import Interactive, TraceTuple
from sapp.models import (
    Issue,
    IssueInstance,
    IssueInstanceSharedTextAssoc,
    IssueInstanceTraceFrameAssoc,
    Run,
    RunStatus,
    SharedText,
    SharedTextKind,
    SourceLocation,
    TraceFrame,
    TraceFrameLeafAssoc,
    TraceKind,
)


class InteractiveTest(TestCase):
    def setUp(self) -> None:
        self.db = DB("memory")
        self.interactive = Interactive("memory", "")
        self.interactive.db = self.db  # we need the tool to refer to the same db
        self.stdout = StringIO()
        self.stderr = StringIO()
        sys.stdout = self.stdout  # redirect output
        sys.stderr = self.stderr  # redirect output

    def tearDown(self) -> None:
        sys.stdout = sys.__stdout__  # reset redirect
        sys.stderr = sys.__stderr__  # reset redirect

    def _clear_stdout(self):
        self.stdout = StringIO()
        sys.stdout = self.stdout

    def _add_to_session(self, session, data):
        if not isinstance(data, list):
            session.add(data)
            return

        for row in data:
            session.add(row)

    def testListIssuesBasic(self):
        issues = [
            Issue(
                id=1,
                handle="1",
                first_seen=datetime.now(),
                code=1000,
                callable="module.function1",
            ),
            Issue(
                id=2,
                handle="2",
                first_seen=datetime.now(),
                code=1001,
                callable="module.function2",
            ),
        ]

        message = SharedText(id=1, contents="message1")
        run = Run(id=1, date=datetime.now())

        issue_instance = IssueInstance(
            id=1,
            run_id=1,
            message_id=1,
            filename="module.py",
            location=SourceLocation(1, 2, 3),
            issue_id=1,
        )

        with self.db.make_session() as session:
            self._add_to_session(session, issues)
            session.add(message)
            session.add(run)
            session.add(issue_instance)
            session.commit()

        self.interactive.setup()
        self.interactive.issues()
        output = self.stdout.getvalue().strip()

        self.assertIn("Issue 1", output)
        self.assertIn("Code: 1000", output)
        self.assertIn("Message: message1", output)
        self.assertIn("Callable: module.function1", output)
        self.assertIn("Location: module.py:1|2|3", output)
        self.assertNotIn("module.function2", output)

    def testListIssuesFromLatestRun(self):
        issue = Issue(
            id=1,
            handle="1",
            first_seen=datetime.now(),
            code=1000,
            callable="module.function1",
        )

        message = SharedText(id=1, contents="message1")
        runs = [
            Run(id=1, date=datetime.now(), status=RunStatus.FINISHED),
            Run(id=2, date=datetime.now(), status=RunStatus.FINISHED),
        ]

        issue_instances = [
            IssueInstance(
                id=1,
                run_id=1,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=1,
            ),
            IssueInstance(
                id=2,
                run_id=2,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=1,
            ),
        ]

        with self.db.make_session() as session:
            session.add(issue)
            session.add(message)
            self._add_to_session(session, runs)
            self._add_to_session(session, issue_instances)
            session.commit()

        self.interactive.setup()
        self.interactive.issues()
        output = self.stdout.getvalue().strip()

        self.assertNotIn("Issue 1", output)
        self.assertIn("Issue 2", output)

    def _list_issues_filter_setup(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        issues = [
            Issue(
                id=1,
                handle="1",
                first_seen=datetime.now(),
                code=1000,
                callable="module.sub.function1",
                filename="module/sub.py",
            ),
            Issue(
                id=2,
                handle="2",
                first_seen=datetime.now(),
                code=1001,
                callable="module.sub.function2",
                filename="module/sub.py",
            ),
            Issue(
                id=3,
                handle="3",
                first_seen=datetime.now(),
                code=1002,
                callable="module.function3",
                filename="module/__init__.py",
            ),
        ]
        issue_instances = [
            IssueInstance(
                id=1,
                run_id=1,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=1,
            ),
            IssueInstance(
                id=2,
                run_id=1,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=2,
            ),
            IssueInstance(
                id=3,
                run_id=1,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=3,
            ),
        ]

        with self.db.make_session() as session:
            session.add(run)
            self._add_to_session(session, issues)
            self._add_to_session(session, issue_instances)
            session.commit()

    def testListIssuesFilterCodes(self):
        self._list_issues_filter_setup()

        self.interactive.setup()
        self.interactive.issues(codes=1000)
        stderr = self.stderr.getvalue().strip()
        self.assertIn("'codes' should be a list", stderr)

        self.interactive.issues(codes=[1000])
        output = self.stdout.getvalue().strip()
        self.assertIn("Issue 1", output)
        self.assertNotIn("Issue 2", output)
        self.assertNotIn("Issue 3", output)

        self._clear_stdout()
        self.interactive.issues(codes=[1001, 1002])
        output = self.stdout.getvalue().strip()
        self.assertNotIn("Issue 1", output)
        self.assertIn("Issue 2", output)
        self.assertIn("Issue 3", output)

    def testListIssuesFilterCallables(self):
        self._list_issues_filter_setup()

        self.interactive.setup()
        self.interactive.issues(callables="function3")
        stderr = self.stderr.getvalue().strip()
        self.assertIn("'callables' should be a list", stderr)

        self.interactive.issues(callables=["%sub%"])
        output = self.stdout.getvalue().strip()
        self.assertIn("Issue 1", output)
        self.assertIn("Issue 2", output)
        self.assertNotIn("Issue 3", output)

        self._clear_stdout()
        self.interactive.issues(callables=["%function3"])
        output = self.stdout.getvalue().strip()
        self.assertNotIn("Issue 1", output)
        self.assertNotIn("Issue 2", output)
        self.assertIn("Issue 3", output)

    def testListIssuesFilterFilenames(self):
        self._list_issues_filter_setup()

        self.interactive.setup()
        self.interactive.issues(filenames="hello.py")
        stderr = self.stderr.getvalue().strip()
        self.assertIn("'filenames' should be a list", stderr)

        self.interactive.issues(filenames=["module/s%"])
        output = self.stdout.getvalue().strip()
        self.assertIn("Issue 1", output)
        self.assertIn("Issue 2", output)
        self.assertNotIn("Issue 3", output)

        self._clear_stdout()
        self.interactive.issues(filenames=["%__init__.py"])
        output = self.stdout.getvalue().strip()
        self.assertNotIn("Issue 1", output)
        self.assertNotIn("Issue 2", output)
        self.assertIn("Issue 3", output)

    def testNoRunsFound(self):
        self.interactive.setup()
        stderr = self.stderr.getvalue().strip()
        self.assertIn("No runs found.", stderr)

    def testListRuns(self):
        runs = [
            Run(id=1, date=datetime.now(), status=RunStatus.FINISHED),
            Run(id=2, date=datetime.now(), status=RunStatus.INCOMPLETE),
            Run(id=3, date=datetime.now(), status=RunStatus.FINISHED),
        ]

        with self.db.make_session() as session:
            self._add_to_session(session, runs)
            session.commit()

        self.interactive.setup()
        self.interactive.runs()
        output = self.stdout.getvalue().strip()

        self.assertIn("Run 1", output)
        self.assertNotIn("Run 2", output)
        self.assertIn("Run 3", output)

    def testSetRun(self):
        runs = [
            Run(id=1, date=datetime.now(), status=RunStatus.FINISHED),
            Run(id=2, date=datetime.now(), status=RunStatus.FINISHED),
        ]
        issue = Issue(
            id=1,
            handle="1",
            first_seen=datetime.now(),
            code=1000,
            callable="module.function1",
        )
        issue_instances = [
            IssueInstance(
                id=1,
                run_id=1,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=1,
            ),
            IssueInstance(
                id=2,
                run_id=2,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=1,
            ),
        ]

        with self.db.make_session() as session:
            self._add_to_session(session, runs)
            self._add_to_session(session, issue_instances)
            session.add(issue)
            session.commit()

        self.interactive.setup()
        self.interactive.set_run(1)
        self.interactive.issues()
        output = self.stdout.getvalue().strip()

        self.assertIn("Issue 1", output)
        self.assertNotIn("Issue 2", output)

    def testSetRunNonExistent(self):
        runs = [
            Run(id=1, date=datetime.now(), status=RunStatus.FINISHED),
            Run(id=2, date=datetime.now(), status=RunStatus.INCOMPLETE),
        ]

        with self.db.make_session() as session:
            self._add_to_session(session, runs)
            session.commit()

        self.interactive.setup()
        self.interactive.set_run(2)
        self.interactive.set_run(3)
        stderr = self.stderr.getvalue().strip()

        self.assertIn("Run 2 doesn't exist", stderr)
        self.assertIn("Run 3 doesn't exist", stderr)

    def testSetIssue(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        issue = Issue(
            id=1,
            handle="1",
            first_seen=datetime.now(),
            code=1000,
            callable="module.function1",
        )
        issue_instances = [
            IssueInstance(
                id=1,
                run_id=1,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=1,
            ),
            IssueInstance(
                id=2,
                run_id=2,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=1,
            ),
            IssueInstance(
                id=3,
                run_id=3,
                message_id=1,
                filename="module.py",
                location=SourceLocation(1, 2, 3),
                issue_id=1,
            ),
        ]

        with self.db.make_session() as session:
            session.add(run)
            session.add(issue)
            self._add_to_session(session, issue_instances)
            session.commit()

        self.interactive.setup()

        self.interactive.set_issue(2)
        self.interactive.show()
        stdout = self.stdout.getvalue().strip()
        self.assertNotIn("Issue 1", stdout)
        self.assertIn("Issue 2", stdout)
        self.assertNotIn("Issue 3", stdout)

        self.interactive.set_issue(1)
        self.interactive.show()
        stdout = self.stdout.getvalue().strip()
        self.assertIn("Issue 1", stdout)
        self.assertNotIn("Issue 3", stdout)

    def testSetIssueNonExistent(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)

        with self.db.make_session() as session:
            session.add(run)
            session.commit()

        self.interactive.setup()
        self.interactive.set_issue(1)
        stderr = self.stderr.getvalue().strip()

        self.assertIn("Issue 1 doesn't exist", stderr)

    def testGetSources(self):
        issue_instance = IssueInstance(
            id=1,
            run_id=1,
            message_id=1,
            filename="module.py",
            location=SourceLocation(1, 2, 3),
            issue_id=1,
        )
        sources = [
            SharedText(id=1, contents="source1", kind=SharedTextKind.SOURCE),
            SharedText(id=2, contents="source2", kind=SharedTextKind.SOURCE),
            SharedText(id=3, contents="source3", kind=SharedTextKind.SOURCE),
        ]
        assocs = [
            IssueInstanceSharedTextAssoc(shared_text_id=1, issue_instance_id=1),
            IssueInstanceSharedTextAssoc(shared_text_id=2, issue_instance_id=1),
        ]

        with self.db.make_session() as session:
            session.add(issue_instance)
            self._add_to_session(session, sources)
            self._add_to_session(session, assocs)
            session.commit()

            sources = self.interactive._get_leaves(
                session, issue_instance, SharedTextKind.SOURCE
            )

        self.assertEqual(len(sources), 2)
        self.assertIn("source1", sources)
        self.assertIn("source2", sources)

    def testGetSinks(self):
        return
        issue_instance = IssueInstance(
            id=1,
            run_id=1,
            message_id=1,
            filename="module.py",
            location=SourceLocation(1, 2, 3),
            issue_id=1,
        )
        sinks = [
            SharedText(id=1, contents="sink1", kind=SharedTextKind.SINK),
            SharedText(id=2, contents="sink2", kind=SharedTextKind.SINK),
            SharedText(id=3, contents="sink3", kind=SharedTextKind.SINK),
        ]
        assocs = [
            IssueInstanceSharedTextAssoc(shared_text_id=1, issue_instance_id=1),
            IssueInstanceSharedTextAssoc(shared_text_id=2, issue_instance_id=1),
        ]

        with self.db.make_session() as session:
            session.add(issue_instance)
            self._add_to_session(session, sinks)
            self._add_to_session(session, assocs)
            session.commit()

            sinks = self.interactive._get_leaves(
                session, issue_instance, SharedTextKind.SINK
            )

        self.assertEqual(len(sinks), 2)
        self.assertIn("sink1", sinks)
        self.assertIn("sink2", sinks)

    def _basic_trace_frames(self):
        return [
            TraceFrame(
                id=1,
                kind=TraceKind.POSTCONDITION,
                caller="call1",
                caller_port="result",
                callee="call2",
                callee_port="formal",
                callee_location=SourceLocation(1, 1),
                filename="file.py",
                run_id=1,
            ),
            TraceFrame(
                id=2,
                kind=TraceKind.PRECONDITION,
                caller="call2",
                caller_port="formal",
                callee="leaf",
                callee_port="sink",
                callee_location=SourceLocation(1, 2),
                filename="file.py",
                run_id=1,
            ),
        ]

    def testNextTraceFrame(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        trace_frames = self._basic_trace_frames()
        sink = SharedText(id=1, contents="sink1", kind=SharedTextKind.SINK)
        assoc = TraceFrameLeafAssoc(trace_frame_id=2, leaf_id=1, trace_length=1)
        with self.db.make_session() as session:
            self._add_to_session(session, trace_frames)
            session.add(run)
            session.add(sink)
            session.add(assoc)
            session.commit()

            self.interactive.setup()
            self.interactive.sources = {"sink1"}
            next_frames = self.interactive._next_trace_frames(session, trace_frames[0])
            self.assertEqual(len(next_frames), 1)
            self.assertEqual(int(next_frames[0].id), int(trace_frames[1].id))

    def testNavigateTraceFrames(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        trace_frames = self._basic_trace_frames()
        sink = SharedText(id=1, contents="sink1", kind=SharedTextKind.SINK)
        assoc = TraceFrameLeafAssoc(trace_frame_id=2, leaf_id=1, trace_length=1)
        with self.db.make_session() as session:
            self._add_to_session(session, trace_frames)
            session.add(run)
            session.add(sink)
            session.add(assoc)
            session.commit()

            self.interactive.setup()
            self.interactive.sources = {"sink1"}
            result = self.interactive._navigate_trace_frames(session, [trace_frames[0]])
            self.assertEqual(len(result), 2)
            self.assertEqual(int(result[0][0].id), 1)
            self.assertEqual(int(result[1][0].id), 2)

    def testCreateTraceTuples(self):
        # reverse order
        postcondition_traces = [
            (
                TraceFrame(
                    callee="call3",
                    callee_port="result",
                    filename="file3.py",
                    callee_location=SourceLocation(1, 1, 3),
                    caller="main",
                    caller_port="root",
                ),
                1,
            ),
            (
                TraceFrame(
                    callee="call2",
                    callee_port="result",
                    caller="dummy caller",
                    filename="file2.py",
                    callee_location=SourceLocation(1, 1, 2),
                ),
                2,
            ),
            (
                TraceFrame(
                    callee="leaf",
                    callee_port="source",
                    caller="dummy caller",
                    filename="file1.py",
                    callee_location=SourceLocation(1, 1, 1),
                ),
                3,
            ),
        ]
        trace_tuples = self.interactive._create_trace_tuples(postcondition_traces)
        self.assertEqual(len(trace_tuples), 3)
        self.assertEqual(
            trace_tuples,
            [
                TraceTuple(postcondition_traces[0][0], 1),
                TraceTuple(postcondition_traces[1][0], 2),
                TraceTuple(postcondition_traces[2][0], 3),
            ],
        )

    def testOutputTraceTuples(self):
        trace_tuples = [
            TraceTuple(
                trace_frame=TraceFrame(
                    callee="leaf",
                    callee_port="source",
                    filename="file1.py",
                    callee_location=SourceLocation(1, 1, 1),
                )
            ),
            TraceTuple(
                trace_frame=TraceFrame(
                    callee="call2",
                    callee_port="result",
                    filename="file2.py",
                    callee_location=SourceLocation(1, 1, 2),
                )
            ),
            TraceTuple(
                trace_frame=TraceFrame(
                    callee="call3",
                    callee_port="result",
                    filename="file3.py",
                    callee_location=SourceLocation(1, 1, 3),
                )
            ),
            TraceTuple(
                trace_frame=TraceFrame(
                    callee="main",
                    callee_port="root",
                    filename="file4.py",
                    callee_location=SourceLocation(1, 1, 4),
                )
            ),
            TraceTuple(
                trace_frame=TraceFrame(
                    callee="call4",
                    callee_port="param0",
                    filename="file4.py",
                    callee_location=SourceLocation(1, 1, 4),
                )
            ),
            TraceTuple(
                trace_frame=TraceFrame(
                    callee="call5",
                    callee_port="param1",
                    filename="file5.py",
                    callee_location=SourceLocation(1, 1, 5),
                )
            ),
            TraceTuple(
                trace_frame=TraceFrame(
                    callee="leaf",
                    callee_port="sink",
                    filename="file6.py",
                    callee_location=SourceLocation(1, 1, 6),
                )
            ),
        ]
        self.interactive.current_trace_frame_index = 1
        self.interactive._output_trace_tuples(trace_tuples)
        output = self.stdout.getvalue()
        self.assertEqual(
            output.split("\n"),
            [
                "     [branches] [callable] [port] [location]",
                "                leaf       source file1.py:1|1|1",
                " -->            call2      result file2.py:1|1|2",
                "                call3      result file3.py:1|1|3",
                "                main       root   file4.py:1|1|4",
                "                call4      param0 file4.py:1|1|4",
                "                call5      param1 file5.py:1|1|5",
                "                leaf       sink   file6.py:1|1|6",
                "",
            ],
        )

        self._clear_stdout()
        self.interactive.current_trace_frame_index = 4
        self.interactive._output_trace_tuples(trace_tuples)
        output = self.stdout.getvalue()
        self.assertEqual(
            output.split("\n"),
            [
                "     [branches] [callable] [port] [location]",
                "                leaf       source file1.py:1|1|1",
                "                call2      result file2.py:1|1|2",
                "                call3      result file3.py:1|1|3",
                "                main       root   file4.py:1|1|4",
                " -->            call4      param0 file4.py:1|1|4",
                "                call5      param1 file5.py:1|1|5",
                "                leaf       sink   file6.py:1|1|6",
                "",
            ],
        )

    def testTrace(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        issue = Issue(
            id=1, handle="1", first_seen=datetime.now(), code=1000, callable="call1"
        )
        issue_instance = IssueInstance(
            id=1,
            run_id=1,
            message_id=1,
            filename="file.py",
            location=SourceLocation(1, 1, 1),
            issue_id=1,
        )
        trace_frames = [
            TraceFrame(
                id=1,
                kind=TraceKind.POSTCONDITION,
                caller="call1",
                caller_port="root",
                callee="leaf",
                callee_port="source",
                callee_location=SourceLocation(1, 1, 1),
                filename="file.py",
                run_id=1,
            ),
            TraceFrame(
                id=2,
                kind=TraceKind.PRECONDITION,
                caller="call1",
                caller_port="root",
                callee="leaf",
                callee_port="sink",
                callee_location=SourceLocation(1, 1, 2),
                filename="file.py",
                run_id=1,
            ),
        ]
        assocs = [
            IssueInstanceTraceFrameAssoc(trace_frame_id=1, issue_instance_id=1),
            IssueInstanceTraceFrameAssoc(trace_frame_id=2, issue_instance_id=1),
            TraceFrameLeafAssoc(trace_frame_id=1, leaf_id=1),
            TraceFrameLeafAssoc(trace_frame_id=2, leaf_id=1),
        ]

        with self.db.make_session() as session:
            session.add(run)
            session.add(issue)
            session.add(issue_instance)
            self._add_to_session(session, trace_frames)
            self._add_to_session(session, assocs)
            session.commit()

        self.interactive.setup()
        self.interactive.trace()
        stderr = self.stderr.getvalue().strip()
        self.assertIn("Use 'set_issue(ID)' to select an issue first.", stderr)

        self.interactive.set_issue(1)
        self.interactive.trace()
        output = self.stdout.getvalue().strip()
        self.assertIn("                leaf       source file.py:1|1|1", output)
        self.assertIn(" -->            call1      root   file.py:1|1|2", output)
        self.assertIn("                leaf       sink   file.py:1|1|2", output)

    def testTraceMissingFrames(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        issue = Issue(
            id=1, handle="1", first_seen=datetime.now(), code=1000, callable="call1"
        )
        issue_instance = IssueInstance(
            id=1,
            run_id=1,
            message_id=1,
            filename="file.py",
            location=SourceLocation(1, 1, 1),
            issue_id=1,
        )
        trace_frames = [
            TraceFrame(
                id=1,
                kind=TraceKind.POSTCONDITION,
                caller="call1",
                caller_port="root",
                callee="leaf",
                callee_port="source",
                callee_location=SourceLocation(1, 1, 1),
                filename="file.py",
                run_id=1,
            ),
            TraceFrame(
                id=2,
                kind=TraceKind.PRECONDITION,
                caller="call1",
                caller_port="root",
                callee="call2",
                callee_port="param0",
                callee_location=SourceLocation(1, 1, 1),
                filename="file.py",
                run_id=1,
            ),
        ]
        assocs = [
            IssueInstanceTraceFrameAssoc(trace_frame_id=1, issue_instance_id=1),
            IssueInstanceTraceFrameAssoc(trace_frame_id=2, issue_instance_id=1),
            TraceFrameLeafAssoc(trace_frame_id=1, leaf_id=1),
            TraceFrameLeafAssoc(trace_frame_id=2, leaf_id=1),
        ]

        with self.db.make_session() as session:
            session.add(run)
            session.add(issue)
            session.add(issue_instance)
            self._add_to_session(session, trace_frames)
            self._add_to_session(session, assocs)
            session.commit()

        self.interactive.setup()
        self.interactive.set_issue(1)
        self.interactive.trace()
        stdout = self.stdout.getvalue().strip()
        self.assertIn("Missing trace frame: call2:param0", stdout)

    def testTraceCursorLocation(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        issue = Issue(
            id=1,
            handle="1",
            first_seen=datetime.now(),
            code=1000,
            callable="module.function1",
        )
        issue_instance = IssueInstance(
            id=1,
            run_id=1,
            message_id=1,
            filename="module.py",
            location=SourceLocation(1, 2, 3),
            issue_id=1,
        )
        trace_frames = [
            TraceFrame(
                id=1,
                kind=TraceKind.POSTCONDITION,
                caller="call1",
                caller_port="root",
                callee="leaf",
                callee_port="source",
                callee_location=SourceLocation(1, 1),
                filename="file.py",
                run_id=1,
            ),
            TraceFrame(
                id=2,
                kind=TraceKind.PRECONDITION,
                caller="call1",
                caller_port="root",
                callee="leaf",
                callee_port="sink",
                callee_location=SourceLocation(1, 2),
                filename="file.py",
                run_id=1,
            ),
        ]
        assocs = [
            IssueInstanceTraceFrameAssoc(trace_frame_id=1, issue_instance_id=1),
            IssueInstanceTraceFrameAssoc(trace_frame_id=2, issue_instance_id=1),
            TraceFrameLeafAssoc(trace_frame_id=1, leaf_id=1),
            TraceFrameLeafAssoc(trace_frame_id=2, leaf_id=1),
        ]
        with self.db.make_session() as session:
            session.add(run)
            session.add(issue)
            session.add(issue_instance)
            self._add_to_session(session, trace_frames)
            self._add_to_session(session, assocs)
            session.commit()

        self.interactive.setup()
        self.interactive.set_issue(1)
        self.assertEqual(self.interactive.current_trace_frame_index, 1)
        self.interactive.next_cursor_location()
        self.assertEqual(self.interactive.current_trace_frame_index, 2)
        self.interactive.next_cursor_location()
        self.assertEqual(self.interactive.current_trace_frame_index, 2)
        self.interactive.prev_cursor_location()
        self.assertEqual(self.interactive.current_trace_frame_index, 1)
        self.interactive.prev_cursor_location()
        self.assertEqual(self.interactive.current_trace_frame_index, 0)
        self.interactive.prev_cursor_location()
        self.assertEqual(self.interactive.current_trace_frame_index, 0)

    def _set_up_branched_trace(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        issue = Issue(
            id=1,
            handle="1",
            first_seen=datetime.now(),
            code=1000,
            callable="module.function1",
        )
        issue_instance = IssueInstance(
            id=1,
            run_id=1,
            message_id=1,
            filename="module.py",
            location=SourceLocation(1, 2, 3),
            issue_id=1,
        )
        messages = [
            SharedText(id=1, contents="source1", kind=SharedTextKind.SOURCE),
            SharedText(id=2, contents="sink1", kind=SharedTextKind.SINK),
        ]
        trace_frames = []
        assocs = [
            IssueInstanceSharedTextAssoc(issue_instance_id=1, shared_text_id=1),
            IssueInstanceSharedTextAssoc(issue_instance_id=1, shared_text_id=2),
        ]
        for i in range(6):
            trace_frames.append(
                TraceFrame(
                    id=i + 1,
                    caller="call1",
                    caller_port="root",
                    filename="file.py",
                    callee_location=SourceLocation(i, i, i),
                    run_id=1,
                )
            )
            if i < 2:  # 2 postconditions
                trace_frames[i].kind = TraceKind.POSTCONDITION
                trace_frames[i].callee = "leaf"
                trace_frames[i].callee_port = "source"
                assocs.append(
                    TraceFrameLeafAssoc(trace_frame_id=i + 1, leaf_id=1, trace_length=0)
                )
                assocs.append(
                    IssueInstanceTraceFrameAssoc(
                        trace_frame_id=i + 1, issue_instance_id=1
                    )
                )
            elif i < 4:
                trace_frames[i].kind = TraceKind.PRECONDITION
                trace_frames[i].callee = "call2"
                trace_frames[i].callee_port = "param2"
                assocs.append(
                    TraceFrameLeafAssoc(trace_frame_id=i + 1, leaf_id=2, trace_length=1)
                )
                assocs.append(
                    IssueInstanceTraceFrameAssoc(
                        trace_frame_id=i + 1, issue_instance_id=1
                    )
                )
            else:
                trace_frames[i].kind = TraceKind.PRECONDITION
                trace_frames[i].caller = "call2"
                trace_frames[i].caller_port = "param2"
                trace_frames[i].callee = "leaf"
                trace_frames[i].callee_port = "sink"
                assocs.append(
                    TraceFrameLeafAssoc(trace_frame_id=i + 1, leaf_id=2, trace_length=0)
                )

        with self.db.make_session() as session:
            session.add(run)
            session.add(issue)
            session.add(issue_instance)
            self._add_to_session(session, messages)
            self._add_to_session(session, trace_frames)
            self._add_to_session(session, assocs)
            session.commit()

    def testTraceBranchNumber(self):
        self._set_up_branched_trace()

        self.interactive.setup()
        self.interactive.set_issue(1)

        self.assertEqual(self.interactive.sources, {"source1"})
        self.assertEqual(self.interactive.sinks, {"sink1"})

        self.interactive.trace()
        output = self.stdout.getvalue().strip()
        self.assertIn("     + 2        leaf       source file.py:0|0|0", output)
        self.assertIn(" -->            call1      root   file.py:2|2|2", output)
        self.assertIn("     + 2        call2      param2 file.py:2|2|2", output)
        self.assertIn("     + 2        leaf       sink   file.py:4|4|4", output)

    def testExpand(self):
        self._set_up_branched_trace()

        self.interactive.setup()
        self.interactive.set_issue(1)
        # Parent at root
        self.interactive.prev_cursor_location()
        self.interactive.expand()
        output = self.stdout.getvalue().strip()
        self.assertIn(
            "[*] leaf : source\n        [0 hops: source1]\n        [file.py:0|0|0]",
            output,
        )
        self.assertIn(
            "[1] leaf : source\n        [0 hops: source1]\n        [file.py:1|1|1]",
            output,
        )

        self._clear_stdout()
        # Move to call2:param2
        self.interactive.next_cursor_location()
        self.interactive.next_cursor_location()
        self.interactive.expand()
        output = self.stdout.getvalue().strip()
        self.assertIn(
            "[*] call2 : param2\n        [1 hops: sink1]\n        [file.py:2|2|2]",
            output,
        )
        self.assertIn(
            "[1] call2 : param2\n        [1 hops: sink1]\n        [file.py:3|3|3]",
            output,
        )

        self._clear_stdout()
        # Move to leaf:sink
        self.interactive.next_cursor_location()
        self.interactive.expand()
        output = self.stdout.getvalue().strip()
        self.assertIn(
            "[*] leaf : sink\n        [0 hops: sink1]\n        [file.py:4|4|4]", output
        )
        self.assertIn(
            "[1] leaf : sink\n        [0 hops: sink1]\n        [file.py:5|5|5]", output
        )

    def testGetTraceFrameBranches(self):
        self._set_up_branched_trace()

        self.interactive.setup()
        self.interactive.set_issue(1)
        # Parent at root
        self.interactive.prev_cursor_location()

        with self.db.make_session() as session:
            branches = self.interactive._get_trace_frame_branches(session)
            self.assertEqual(len(branches), 2)
            self.assertEqual(int(branches[0].id), 1)
            self.assertEqual(int(branches[1].id), 2)

            # Parent is no longer root
            self.interactive.next_cursor_location()
            self.interactive.next_cursor_location()
            self.interactive.next_cursor_location()

            branches = self.interactive._get_trace_frame_branches(session)
            self.assertEqual(len(branches), 2)
            self.assertEqual(int(branches[0].id), 5)
            self.assertEqual(int(branches[1].id), 6)

    def testBranch(self):
        self._set_up_branched_trace()

        self.interactive.setup()
        self.interactive.set_issue(1)
        self.interactive.prev_cursor_location()

        # We are testing for the source location, which differs between branches
        self._clear_stdout()
        self.interactive.branch(1)  # location 0|0|0 -> 1|1|1
        output = self.stdout.getvalue().strip()
        self.assertIn(" --> + 2        leaf       source file.py:1|1|1", output)

        self._clear_stdout()
        self.interactive.branch(0)  # location 1|1|1 -> 0|0|0
        output = self.stdout.getvalue().strip()
        self.assertIn(" --> + 2        leaf       source file.py:0|0|0", output)

        self.interactive.next_cursor_location()
        self.interactive.next_cursor_location()

        self._clear_stdout()
        self.interactive.branch(1)  # location 2|2|2 -> 3|3|3
        output = self.stdout.getvalue().strip()
        self.assertIn(" --> + 2        call2      param2 file.py:3|3|3", output)

        self.interactive.next_cursor_location()

        self._clear_stdout()
        self.interactive.branch(1)  # location 4|4|4 -> 5|5|5
        output = self.stdout.getvalue().strip()
        self.assertIn("     + 2        call2      param2 file.py:3|3|3", output)
        self.assertIn(" --> + 2        leaf       sink   file.py:5|5|5", output)

        self.interactive.branch(2)  # location 4|4|4 -> 5|5|5
        stderr = self.stderr.getvalue().strip()
        self.assertIn("out of bounds", stderr)

    def testBranchPrefixLengthChanges(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        issue = Issue(
            id=1,
            handle="1",
            first_seen=datetime.now(),
            code=1000,
            callable="module.function1",
        )
        issue_instance = IssueInstance(
            id=1,
            run_id=1,
            message_id=1,
            filename="module.py",
            location=SourceLocation(1, 2, 3),
            issue_id=1,
        )
        messages = [
            SharedText(id=1, contents="source1", kind=SharedTextKind.SOURCE),
            SharedText(id=2, contents="sink1", kind=SharedTextKind.SINK),
        ]
        trace_frames = [
            TraceFrame(
                id=1,
                kind=TraceKind.POSTCONDITION,
                caller="call1",
                caller_port="root",
                callee="leaf",
                callee_port="source",
                callee_location=SourceLocation(1, 1),
                filename="file.py",
                run_id=1,
            ),
            TraceFrame(
                id=2,
                kind=TraceKind.POSTCONDITION,
                caller="call1",
                caller_port="root",
                callee="prev_call",
                callee_port="result",
                callee_location=SourceLocation(1, 1),
                filename="file.py",
                run_id=1,
            ),
            TraceFrame(
                id=3,
                kind=TraceKind.POSTCONDITION,
                caller="prev_call",
                caller_port="result",
                callee="leaf",
                callee_port="source",
                callee_location=SourceLocation(1, 1),
                filename="file.py",
                run_id=1,
            ),
            TraceFrame(
                id=4,
                kind=TraceKind.PRECONDITION,
                caller="call1",
                caller_port="root",
                callee="leaf",
                callee_port="sink",
                callee_location=SourceLocation(1, 2),
                filename="file.py",
                run_id=1,
            ),
        ]
        assocs = [
            IssueInstanceSharedTextAssoc(issue_instance_id=1, shared_text_id=1),
            IssueInstanceSharedTextAssoc(issue_instance_id=1, shared_text_id=2),
            IssueInstanceTraceFrameAssoc(issue_instance_id=1, trace_frame_id=1),
            IssueInstanceTraceFrameAssoc(issue_instance_id=1, trace_frame_id=2),
            IssueInstanceTraceFrameAssoc(issue_instance_id=1, trace_frame_id=4),
            TraceFrameLeafAssoc(trace_frame_id=1, leaf_id=1, trace_length=0),
            TraceFrameLeafAssoc(trace_frame_id=2, leaf_id=1, trace_length=1),
            TraceFrameLeafAssoc(trace_frame_id=3, leaf_id=1, trace_length=0),
            TraceFrameLeafAssoc(trace_frame_id=4, leaf_id=2, trace_length=0),
        ]
        with self.db.make_session() as session:
            session.add(run)
            session.add(issue)
            session.add(issue_instance)
            self._add_to_session(session, messages)
            self._add_to_session(session, trace_frames)
            self._add_to_session(session, assocs)
            session.commit()

        self.interactive.setup()
        self.interactive.set_issue(1)

        self._clear_stdout()
        self.interactive.prev_cursor_location()
        self.assertEqual(
            self.stdout.getvalue().split("\n"),
            [
                "     [branches] [callable] [port] [location]",
                " --> + 2        leaf       source file.py:1|1|1",
                "                call1      root   file.py:1|2|2",
                "                leaf       sink   file.py:1|2|2",
                "",
            ],
        )

        self._clear_stdout()
        self.interactive.branch(1)
        self.assertEqual(
            self.stdout.getvalue().split("\n"),
            [
                "     [branches] [callable] [port] [location]",
                "                leaf       source file.py:1|1|1",
                " --> + 2        prev_call  result file.py:1|1|1",
                "                call1      root   file.py:1|2|2",
                "                leaf       sink   file.py:1|2|2",
                "",
            ],
        )

        self._clear_stdout()
        self.interactive.expand()
        output = self.stdout.getvalue().strip()
        self.assertIn("[*] prev_call : result", output)
        self.assertIn("        [1 hops: source1]", output)

    def testCurrentBranchIndex(self):
        trace_frames = [TraceFrame(id=1), TraceFrame(id=2), TraceFrame(id=3)]

        self.interactive.current_trace_frame_index = 0
        self.interactive.trace_tuples = [TraceTuple(trace_frame=TraceFrame(id=1))]

        self.assertEqual(0, self.interactive._current_branch_index(trace_frames))
        self.interactive.trace_tuples[0].trace_frame.id = 2
        self.assertEqual(1, self.interactive._current_branch_index(trace_frames))
        self.interactive.trace_tuples[0].trace_frame.id = 3
        self.assertEqual(2, self.interactive._current_branch_index(trace_frames))

        self.interactive.trace_tuples[0].trace_frame.id = 4
        self.assertEqual(-1, self.interactive._current_branch_index(trace_frames))

    def testVerifyMultipleBranches(self):
        # Leads to no-op on _generate_trace
        self.interactive.trace_tuples_id = 1
        self.interactive.current_issue_id = 1

        self.interactive.current_trace_frame_index = 0
        self.interactive.trace_tuples = [
            TraceTuple(trace_frame=TraceFrame(id=1), branches=1),
            TraceTuple(trace_frame=TraceFrame(id=2), branches=2),
        ]
        self.assertFalse(self.interactive._verify_multiple_branches())

        self.interactive.current_trace_frame_index = 1
        self.assertTrue(self.interactive._verify_multiple_branches())

    def mock_pager(self, output_string):
        self.pager_calls += 1

    def testPager(self):
        run = Run(id=1, date=datetime.now(), status=RunStatus.FINISHED)
        issue = Issue(
            id=1,
            handle="1",
            first_seen=datetime.now(),
            code=1000,
            callable="module.function1",
        )
        issue_instance = IssueInstance(
            id=1,
            run_id=1,
            message_id=1,
            filename="module.py",
            location=SourceLocation(1, 2, 3),
            issue_id=1,
        )

        with self.db.make_session() as session:
            session.add(run)
            session.add(issue)
            session.add(issue_instance)
            session.commit()

        # Default is no pager in tests
        self.pager_calls = 0
        with patch("IPython.core.page.page", self.mock_pager):
            self.interactive.setup()
            self.interactive.issues()
            self.interactive.runs()
        self.assertEqual(self.pager_calls, 0)

        self.pager_calls = 0
        with patch("IPython.core.page.page", self.mock_pager):
            self.interactive.setup()
            self.interactive.issues(use_pager=True)
            self.interactive.runs(use_pager=True)
        self.assertEqual(self.pager_calls, 2)
