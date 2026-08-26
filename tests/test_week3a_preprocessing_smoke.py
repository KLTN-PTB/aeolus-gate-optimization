from scripts.smoke_week3a_preprocessing import build_parser


def test_week3a_smoke_defaults_are_bounded_development_only() -> None:
    args = build_parser().parse_args([])

    assert args.train_year == 2016
    assert args.validation_year == 2019
    assert args.train_rows == 1024
    assert args.validation_rows == 512
    assert args.batch_size == 256
