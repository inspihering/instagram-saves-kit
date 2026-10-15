"""Generate a video with Seedance 2.5 through the Higgsfield API.

Credentials come from HF_KEY ("key-id:key-secret"), read from .env.local or the
process environment. The value is never printed or logged.
"""

import sys

import higgsfield_client
from dotenv import load_dotenv

MODEL = 'bytedance/seedance-2.5/text-to-video'
ARGUMENTS = {
    'prompt': 'A cinematic scene at sunset',
    'duration': 5,
    'resolution': '720p',
    'aspect_ratio': '16:9',
}


def video_url(result):
    video = result.get('video')
    if isinstance(video, dict):
        return video.get('url')
    if isinstance(video, list) and video and isinstance(video[0], dict):
        return video[0].get('url')
    if isinstance(video, str):
        return video
    return None


def main():
    # An existing environment variable wins over the file; neither is echoed.
    load_dotenv('.env.local', override=False)

    def on_enqueue(request_id):
        print(f'Request queued: {request_id}')

    def on_queue_update(status):
        print(f'Status: {type(status).__name__}')

    try:
        result = higgsfield_client.subscribe(
            MODEL,
            arguments=ARGUMENTS,
            on_enqueue=on_enqueue,
            on_queue_update=on_queue_update,
        )
    except higgsfield_client.CredentialsMissedError:
        print('HF_KEY is not set. Add it to .env.local as HF_KEY=key-id:key-secret.', file=sys.stderr)
        return 1
    except higgsfield_client.HiggsfieldClientError as error:
        print(f'Higgsfield API error: {error}', file=sys.stderr)
        return 1

    # subscribe() returns normally for failed, nsfw and canceled requests too,
    # so only a "completed" status with a video URL counts as success.
    status = result.get('status')
    if status != 'completed':
        reasons = {
            'failed': 'Generation failed.',
            'nsfw': 'Request was blocked by content moderation.',
            'canceled': 'Request was canceled.',
        }
        print(reasons.get(status, f'Request ended with unexpected status: {status!r}'), file=sys.stderr)
        return 1

    url = video_url(result)
    if not url:
        print('Request completed but the response contained no video URL.', file=sys.stderr)
        return 1

    print(f'Video URL: {url}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
