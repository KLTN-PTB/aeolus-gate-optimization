"""Train and validate the proposal-completion profile without launching a UI."""
import os
import sys
from pathlib import Path
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(key, "8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
def main():
    import argparse
    from datetime import datetime
    import json
    import yaml
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=root / 'configs/thesis_completion.yaml')
    parser.add_argument('--output', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--smoke', action='store_true')
    mode.add_argument('--full', action='store_true')
    parser.add_argument('--stage', choices=['all','models','experiments','verify'], default='all')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        if not args.output:
            parser.error('--status requires --output')
        for name in ('progress.json','summary.json','experiments/progress.json','completion.json'):
            path = args.output / name
            if path.exists():
                print(name, path.read_text(encoding='utf-8'))
        return
    output = (args.output or root / 'artifacts/thesis_completion' / datetime.now().strftime('%Y%m%d_%H%M%S')).resolve()
    if args.stage in ('all','models'):
        summary = output / 'summary.json'
        complete = args.resume and summary.exists() and json.loads(summary.read_text()).get('status') == 'MODELS_COMPLETE'
        if not complete:
            from src.pipeline.thesis_training import main as training_main
            sys.argv = [sys.argv[0], '--config', str(args.config), '--output', str(output)]
            if args.smoke:
                sys.argv.append('--smoke')
            if args.resume:
                sys.argv.append('--resume')
            training_main()
    if args.smoke or args.stage == 'models':
        return
    frozen_config = json.loads((output / 'resolved_config.json').read_text())
    if yaml.safe_load(args.config.read_text(encoding='utf-8')) != frozen_config:
        raise ValueError('Later stages and resume must use the exact frozen configuration')
    from src.pipeline.thesis_release import activate, repack_legacy
    activate(output)
    repack_legacy(output)
    if args.stage in ('all','experiments'):
        from src.pipeline.thesis_experiments import Experiments
        Experiments(output, yaml.safe_load(args.config.read_text(encoding='utf-8'))).run()
    if args.stage in ('all','verify'):
        from src.pipeline.thesis_verification import verify
        verify(output)


if __name__ == '__main__':
    main()
