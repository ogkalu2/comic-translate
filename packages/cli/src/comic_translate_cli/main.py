"""
Comic Translate CLI main entry point.
"""

import click
from typing import Optional


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Comic Translate - Translate comic images."""
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--source-lang", "-s", default="Japanese", help="Source language")
@click.option("--target-lang", "-t", default="English", help="Target language")
@click.option("--ocr-engine", default="manga_ocr", help="OCR engine to use")
@click.option("--translator", default="gpt", help="Translation engine to use")
@click.option("--inpainter", default="lama", help="Inpainting engine to use")
def translate(
    input_path: str,
    output: Optional[str],
    source_lang: str,
    target_lang: str,
    ocr_engine: str,
    translator: str,
    inpainter: str,
):
    """Translate comic images."""
    click.echo(f"Translating {input_path}")
    click.echo(f"Source: {source_lang} -> Target: {target_lang}")
    click.echo(f"OCR: {ocr_engine}, Translator: {translator}, Inpainter: {inpainter}")
    # TODO: Implement translation pipeline


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output directory")
def detect(input_path: str, output: Optional[str]):
    """Detect panels and bubbles in comic images."""
    click.echo(f"Detecting in {input_path}")
    # TODO: Implement detection pipeline


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--engine", default="manga_ocr", help="OCR engine to use")
def ocr(input_path: str, output: Optional[str], engine: str):
    """Extract text from comic images using OCR."""
    click.echo(f"Running OCR on {input_path} with {engine}")
    # TODO: Implement OCR pipeline


if __name__ == "__main__":
    cli()
