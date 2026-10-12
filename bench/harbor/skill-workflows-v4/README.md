# Complete response contracts and fresh difficulty screening

This separate experimental package applies the reviewed response-contract correction and supports one **eight-task, 16-trial upstream-only development screen**. It cannot dispatch a held-out comparison. See [PROTOCOL.md](PROTOCOL.md) for the prospective gate and conditions.

The original v1/v2/v3 studies, graders and public replayers stay unchanged. `FORK_PROVENANCE.json` records the initial namespace fork from the completed v3 implementation; it is provenance, not a claim that every forked file remains identical. Obsolete multi-arm analysis, ablation and second-round admission were removed from this package.

```sh
python3 -I -B bench/harbor/skill-workflows-v4/run.py preserve
python3 -I -B -m pytest -p no:cacheprovider -rs bench/harbor/skill-workflows-v4/tests
```

Docker integration controls require explicit local image/upstream inputs. Their `EVALOPT_V4_*_CONTROL` environment variable names select fixtures only; they never select or resume an old campaign. A run with skipped prerequisites is not live admission. No test invokes a model. Live preparation requires a separately reviewed, source-bound admission receipt, exact runtime availability and an external freeze digest.

Structured reports refer to an immutable initial observation ID. The stopped candidate receives a separate post-stop check. Claim support is computed against the supplied observation; final functional grading and acceptance use the relevant stopped evidence. Reporting validity and task difficulty remain separate.
