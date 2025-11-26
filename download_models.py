"""
Script to download all models before first use.
Ensures faster API responses by pre-downloading all models.
"""

import requests
import sys
import time


def check_server(base_url="http://localhost:8000"):
    """Check if the server is running."""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def get_model_status(base_url="http://localhost:8000"):
    """Get current model download status."""
    try:
        response = requests.get(f"{base_url}/api/v1/models")
        return response.json()
    except Exception as e:
        print(f"Error getting model status: {e}")
        return None


def download_models(base_url="http://localhost:8000", categories=None):
    """Download models for specified categories."""
    try:
        print("Starting model download...")
        print("This may take several minutes depending on your internet speed.")
        print()
        
        response = requests.post(
            f"{base_url}/api/v1/models/download",
            json=categories,
            timeout=600  # 10 minute timeout for large downloads
        )
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("Download timed out. This can happen with slow connections.")
        print("The models may still be downloading in the background.")
        return None
    except Exception as e:
        print(f"Error downloading models: {e}")
        return None


def main():
    base_url = "http://localhost:8000"
    
    print("=" * 60)
    print("Manga Translation API - Model Downloader")
    print("=" * 60)
    print()
    
    # Check if server is running
    print("Checking if server is running...")
    if not check_server(base_url):
        print("✗ Server is not running!")
        print()
        print("Please start the server first:")
        print("  uv run python run_server.py")
        print()
        sys.exit(1)
    
    print("✓ Server is running")
    print()
    
    # Check current model status
    print("Checking current model status...")
    status = get_model_status(base_url)
    
    if status:
        summary = status['summary']
        print(f"  Total models: {summary['total']}")
        print(f"  Downloaded: {summary['downloaded']}")
        print(f"  Pending: {summary['pending']}")
        print()
        
        if summary['pending'] == 0:
            print("✓ All models are already downloaded!")
            print()
            
            # Show what's available
            print("Available models:")
            for category, models in status['models'].items():
                print(f"\n  {category.upper()}:")
                for name, info in models.items():
                    status_icon = "✓" if info['downloaded'] else "✗"
                    print(f"    {status_icon} {name}")
            
            return
    
    # Download models
    print("Downloading core models (detection, OCR, inpainting)...")
    print()
    print("⏳ This will download approximately 350-500 MB of data...")
    print()
    
    result = download_models(base_url)
    
    if result:
        print()
        print("=" * 60)
        print("✓ Download Complete!")
        print("=" * 60)
        print()
        print("Downloaded models:")
        for model in result['downloaded']:
            print(f"  ✓ {model}")
        print()
        print(f"Total: {len(result['downloaded'])} model(s)")
        print()
        print("The API is now ready for fast translations!")
        print()
    else:
        print()
        print("=" * 60)
        print("⚠ Download may have failed or timed out")
        print("=" * 60)
        print()
        print("Tips:")
        print("  - Check your internet connection")
        print("  - Check server logs for details")
        print("  - Models will auto-download on first use")
        print("  - Try again with: uv run python download_models.py")
        print()
    
    # Show final status
    print("Final model status:")
    status = get_model_status(base_url)
    if status:
        summary = status['summary']
        print(f"  Downloaded: {summary['downloaded']}/{summary['total']}")
        print()


if __name__ == "__main__":
    main()
