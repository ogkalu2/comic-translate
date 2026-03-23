import click

from comic_translate_core.pipeline import QAOrchestrator
from comic_translate_core.storage import JsonFileStorage, MockExporter
from comic_translate_qa.applicator import NoopApplicator
from comic_translate_qa.chunking import PageBasedChunking
from comic_translate_qa.providers import OpenAIQAProvider


@click.group()
def cli():
    """Comic Translate QA CLI"""
    pass


@cli.command()
@click.option("--comic-id", required=True)
@click.option("--output", required=True)
def export(comic_id, output):
    """Export mock script for testing"""
    orchestrator = QAOrchestrator(
        exporter=MockExporter(),
        storage=JsonFileStorage(),
        chunking=PageBasedChunking(),
        llm_provider=OpenAIQAProvider(api_key="dummy"),
        applicator=NoopApplicator(),
    )

    script = orchestrator.export_script(
        comic_id=comic_id,
        base_fp="mock_fp",
        source_lang="ja",
        target_lang="zh-hk",
        output_path=output,
    )

    click.echo(f"Exported {len(script.blocks)} blocks to {output}")


@cli.command()
@click.option("--script", required=True)
@click.option("--output", required=True)
@click.option("--api-key", envvar="OPENAI_API_KEY", required=True)
def qa(script, output, api_key):
    """Run QA on script"""
    orchestrator = QAOrchestrator(
        exporter=MockExporter(),
        storage=JsonFileStorage(),
        chunking=PageBasedChunking(),
        llm_provider=OpenAIQAProvider(api_key=api_key),
        applicator=NoopApplicator(),
    )

    patch_set = orchestrator.qa_script(
        script_path=script,
        output_patch_path=output,
    )

    click.echo(f"Generated {len(patch_set.patches)} patches")
    click.echo(f"Summary: {patch_set.summary}")


@cli.command()
@click.option("--patches", required=True)
def apply(patches):
    """Apply patches (dry-run)"""
    orchestrator = QAOrchestrator(
        exporter=MockExporter(),
        storage=JsonFileStorage(),
        chunking=PageBasedChunking(),
        llm_provider=OpenAIQAProvider(api_key="dummy"),
        applicator=NoopApplicator(),
    )

    result = orchestrator.apply_patches(patch_path=patches)

    click.echo(f"Total: {result['total']}")
    click.echo(f"Applied: {result['applied']}")
    click.echo(f"Skipped: {result['skipped']}")


if __name__ == "__main__":
    cli()
