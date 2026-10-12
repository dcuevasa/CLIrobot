"""Tests for recording QoL features and dataset CLI subcommands."""

from typer.testing import CliRunner
from clirobot.cli import app
from clirobot.config.schema import RobotProfile, ArmConfig
from clirobot.integration.args_builder import LeRobotArgsBuilder
from clirobot.ui.hud import build_hud_panel

runner = CliRunner()


def test_build_record_args_qol_features():
    profile = RobotProfile(
        name="so101_desk",
        robot_type="so101",
        teleop_type="so101_leader",
        leader_arm=ArmConfig(port="/dev/ttyACM0"),
        follower_arm=ArmConfig(port="/dev/ttyACM1"),
        dataset_repo_id="dcuevas/so101_demo",
        default_fps=30,
    )

    args = LeRobotArgsBuilder.build_record_args(
        profile,
        num_episodes=5,
        episode_time_s=20.0,
        single_task="pick coffee pod",
        display_data=True,
        play_sounds=True,
        streaming_encoding=True,
        reset_every_episode=True,
        resume=True,
        batch_encoding_size=32,
        private=True,
        tags=["coffee", "so101"],
    )

    assert "--robot.type=so101" in args
    assert "--teleop.type=so101_leader" in args
    assert "--teleop.port=/dev/ttyACM0" in args
    assert "--robot.port=/dev/ttyACM1" in args
    assert "--dataset.repo_id=dcuevas/so101_demo" in args
    assert "--dataset.num_episodes=5" in args
    assert "--dataset.episode_time_s=20.0" in args
    assert "--dataset.single_task=pick coffee pod" in args
    assert "--display_data=true" in args
    assert "--play_sounds=true" in args
    assert "--dataset.streaming_encoding=true" in args
    assert "--robot.reset_every_episode=true" in args
    assert "--resume=true" in args
    assert "--dataset.video_encoding_batch_size=32" in args
    assert "--dataset.private=true" in args
    assert '--dataset.tags=["coffee", "so101"]' in args


def test_hud_panel_qol_badges():
    from io import StringIO
    from rich.console import Console

    panel = build_hud_panel(
        status="RECORDING",
        episode_index=2,
        total_episodes=10,
        fps=30.0,
        qol_features=["Rerun Viz", "Streaming Encode", "Audio Cues"],
    )
    buf = StringIO()
    Console(file=buf, force_terminal=False, width=120).print(panel)
    rendered = buf.getvalue()
    assert "RECORDING" in rendered
    assert "2" in rendered
    assert "10" in rendered
    assert "Rerun Viz" in rendered
    assert "Streaming Encode" in rendered


def test_cli_record_help():
    result = runner.invoke(app, ["record", "--help"])
    assert result.exit_code == 0
    assert "--display-data" in result.output
    assert "--streaming-encoding" in result.output
    assert "--play-sounds" in result.output
    assert "--reset-every-episode" in result.output
    assert "--resume" in result.output


def test_cli_dataset_subcommands_help():
    # prune help
    res_prune = runner.invoke(app, ["dataset", "prune", "--help"])
    assert res_prune.exit_code == 0
    assert "--drop-depth" in res_prune.output
    assert "--drop-ee" in res_prune.output
    assert "--slice-dof" in res_prune.output

    # split help
    res_split = runner.invoke(app, ["dataset", "split", "--help"])
    assert res_split.exit_code == 0
    assert "--annotation-type" in res_split.output
    assert "--subtask" in res_split.output
    assert "--hub-repo-prefix" in res_split.output

    # annotations help
    res_ann = runner.invoke(app, ["dataset", "annotations", "--help"])
    assert res_ann.exit_code == 0
    assert "--repo-id" in res_ann.output
