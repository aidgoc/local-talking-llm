"""Test script for the enhanced TTS module."""

import sounddevice as sd
from rich.console import Console
from tts import TextToSpeechService

console = Console()


def test_tts():
    """Test the enhanced TTS service."""
    console.print("[bold]Testing Enhanced TTS Service[/bold]")

    try:
        # Initialize the TTS service
        console.print("[blue]Initializing TTS service...[/blue]")
        tts = TextToSpeechService()

        # Get the sample rates
        console.print(f"[blue]Source sample rate: {tts.sample_rate}Hz[/blue]")
        console.print(f"[blue]Target sample rate: {tts.target_sample_rate}Hz[/blue]")

        # Test synthesis
        text = "This is a test of the enhanced text to speech system with automatic resampling."
        console.print(f"[blue]Synthesizing: '{text}'[/blue]")

        sample_rate, audio = tts.synthesize(text)
        console.print(f"[green]Synthesis successful! Output sample rate: {sample_rate}Hz[/green]")

        # Play the audio
        console.print("[blue]Playing audio...[/blue]")
        sd.play(audio, sample_rate)
        sd.wait()
        console.print("[green]Audio playback successful![/green]")

        return True
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return False


if __name__ == "__main__":
    test_tts()
