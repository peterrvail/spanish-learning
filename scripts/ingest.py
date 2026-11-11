#!/usr/bin/env python3
"""Turn lesson screenshots into study material.

    python scripts/ingest.py run ~/Desktop/leccion120 --lesson L120
    python scripts/ingest.py status
    python scripts/ingest.py review --approve-high
    python scripts/ingest.py compile

run      reads each new screenshot with Claude (needs ANTHROPIC_API_KEY) and
         writes what it found to data/observations/staged/, as "pending".
         A screenshot already read is skipped, so it is safe to run again.
review   shows pending observations one at a time: approve, edit, reject.
compile  writes the approved ones to data/compiled/lesson_observations.json,
         which the app shows as the "De mis capturas" flashcard deck and the
         "Correcciones de clase" drill. Commit that file and the staged ones.

The screenshots themselves are copied to data/artifacts/raw/ (not in git)."""
import argparse
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ingest import pipeline  # noqa: E402  (also puts app/ on the path)
from ingest.schemas import ArtifactKind  # noqa: E402
import conversation  # noqa: E402

KINDS = ArtifactKind.__args__


def _lesson(value):
    if not re.fullmatch(r"L\d+(\.\d+)?", value):
        raise argparse.ArgumentTypeError("a lesson looks like L120")
    return value


def cmd_run(args):
    images, skipped = pipeline.find_images(args.paths)
    for path, why in skipped:
        print(f"  skipped   {path}: {why}")
    plans = [(path, *pipeline.plan(path, force=args.force, discard_reviews=args.discard_reviews)) for path in images]
    todo = [p for p in plans if p[1] in ("new", "reread")]
    if args.limit is not None:
        todo = todo[:args.limit]
    for path, action, sha, why in plans:
        if action in ("cached", "blocked"):
            print(f"  {action:9} {os.path.basename(path)} [{sha[:12]}] {why}")
    if args.dry_run:
        for path, action, sha, why in todo:
            print(f"  would read {os.path.basename(path)} [{sha[:12]}]" + (f" ({why})" if why else ""))
        print(f"Dry run: {len(todo)} image(s) would be sent to {args.model}; nothing was sent or written.")
        return 0
    if not todo:
        print("Nothing new to read.")
        return 1 if any(p[1] == "blocked" for p in plans) or (skipped and not images) else 0
    if not conversation.credentials_configured():
        print("No Claude API credentials found: set ANTHROPIC_API_KEY and run again.")
        return 1
    client = conversation.get_client()
    failed = 0
    for path, action, sha, why in todo:
        name = os.path.basename(path)
        try:
            obs_file, dropped = pipeline.ingest_image(
                client, path, lesson=args.lesson, kind=args.kind, captured_on=args.date, model=args.model,
                copy=not args.no_copy)
        except pipeline.IngestError as e:
            failed += 1
            print(f"  FAILED    {name} [{sha[:12]}]: {e}")
            continue
        counts = {}
        for o in obs_file.observations:
            counts[o.status] = counts.get(o.status, 0) + 1
        summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items())) or "nothing worth studying found"
        print(f"  read      {name} [{sha[:12]}] lesson {obs_file.artifact.lesson or '-'}: {summary}")
        for line in dropped:
            print(f"            dropped (did not fit the rules) {line}")
    print(f"Done: {len(todo) - failed} read, {failed} failed. Next: python scripts/ingest.py review")
    return 1 if failed else 0


def cmd_status(args):
    staged = pipeline.load_staged()
    if not staged:
        print("No screenshots have been read yet.")
        return 0
    total = {}
    for short, lesson, filename, counts in pipeline.status_rows(staged):
        for status, n in counts.items():
            total[status] = total.get(status, 0) + n
        print(f"  {short}  {lesson:7} {filename[:40]:40} " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
    print(f"{len(staged)} screenshot(s): " + ", ".join(f"{n} {s}" for s, n in sorted(total.items())))
    return 0


def _show(o, artifact, position):
    print(f"\n[{position}] {o.type} · {o.region} · confidence {o.confidence} · "
          f"lesson {artifact.lesson or '-'} · {artifact.filename}")
    print(f"  as written: {o.verbatim}")
    print(f"  spanish:    {o.spanish}")
    print(f"  english:    {o.english or '-'}")
    if o.correction:
        print(f"  wrong:      {o.correction.wrong}")
        print(f"  right:      {o.correction.right}")
        print(f"  why:        {o.correction.why or '-'}")
    if o.concept_ids or o.error_tags:
        print(f"  topics:     {', '.join(o.concept_ids + o.error_tags)}")
    if o.note:
        print(f"  note:       {o.note}")


def cmd_review(args, ask=input):
    staged = [f for f in pipeline.load_staged() if not args.lesson or f.artifact.lesson == args.lesson]
    if args.approve_high:
        approved = 0
        for i, obs_file in enumerate(staged):
            staged[i], n = pipeline.approve_high(obs_file)
            if n:
                pipeline.save_staged(staged[i])
            approved += n
        print(f"Approved {approved} high-confidence word(s) and expression(s).")
    pending = [(i, o.id) for i, f in enumerate(staged) for o in f.observations if o.status == "pending"]
    if not pending:
        print("Nothing left to review. Next: python scripts/ingest.py compile")
        return 0
    print(f"{len(pending)} to review.  [a]pprove  [e]dit  [r]eject  [s]kip  [q]uit")
    done = 0
    for n, (i, oid) in enumerate(pending, 1):
        while True:
            o = next(x for x in staged[i].observations if x.id == oid)
            _show(o, staged[i].artifact, f"{n}/{len(pending)}")
            try:
                answer = ask("  a/e/r/s/q > ").strip().lower()[:1]
            except EOFError:
                answer = "q"
            if answer == "q":
                print(f"Stopped. {done} reviewed, {len(pending) - done} still pending.")
                return 0
            if answer == "s":
                break
            if answer in ("a", "r"):
                staged[i] = pipeline.decide(staged[i], oid, "approved" if answer == "a" else "rejected")
                pipeline.save_staged(staged[i])
                done += 1
                break
            if answer == "e":
                fields = [f for f in pipeline.EDITABLE if o.correction or f not in ("wrong", "right", "why")]
                field = ask(f"  field ({' / '.join(fields)}) > ").strip().lower()
                if field not in fields:
                    print("  not one of those fields")
                    continue
                try:
                    staged[i] = pipeline.decide(staged[i], oid, "pending", **{field: ask(f"  new {field} > ")})
                    pipeline.save_staged(staged[i])
                except ValueError as e:
                    print(f"  not saved: {str(e).splitlines()[-1].strip()}")
    print(f"Reviewed {done}. Next: python scripts/ingest.py compile")
    return 0


def cmd_compile(args):
    compiled = pipeline.compile_observations(pipeline.load_staged())
    changed = pipeline.write_compiled(compiled)
    print(f"{len(compiled['cards'])} flashcards, {len(compiled['corrections'])} corrections, "
          f"{len(compiled['rule_notes'])} rule notes -> data/compiled/lesson_observations.json "
          f"({'updated' if changed else 'no change'}).")
    if changed:
        print("Commit data/observations/staged/ and data/compiled/ to publish them to the app.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="read new screenshots with Claude")
    run.add_argument("paths", nargs="+", help="image files or folders")
    run.add_argument("--lesson", type=_lesson, help="lesson these are from, e.g. L120")
    run.add_argument("--kind", choices=KINDS, help="what the screenshots are (default: Claude decides)")
    run.add_argument("--date", type=date.fromisoformat, help="date of the lesson, YYYY-MM-DD")
    run.add_argument("--model", default=conversation.MODEL, help=f"default {conversation.MODEL}")
    run.add_argument("--dry-run", action="store_true", help="show what would be read; send and write nothing")
    run.add_argument("--force", action="store_true", help="read again an image that was already read")
    run.add_argument("--discard-reviews", action="store_true",
                     help="with --force: allow losing review decisions already made on that image")
    run.add_argument("--limit", type=int, help="read at most this many new images")
    run.add_argument("--no-copy", action="store_true", help="don't copy images into data/artifacts/raw/")
    run.set_defaults(func=cmd_run)
    sub.add_parser("status", help="what has been read and reviewed").set_defaults(func=cmd_status)
    review = sub.add_parser("review", help="approve, edit or reject pending observations")
    review.add_argument("--lesson", type=_lesson, help="only this lesson")
    review.add_argument("--approve-high", action="store_true",
                        help="first approve every high-confidence word and expression")
    review.set_defaults(func=cmd_review)
    sub.add_parser("compile", help="write approved observations for the app").set_defaults(func=cmd_compile)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
