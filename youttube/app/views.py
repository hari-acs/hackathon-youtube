from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from youtube_transcript_api import YouTubeTranscriptApi
from gtts import gTTS
from io import BytesIO
from django.template import loader
from pydub import AudioSegment
from pytube import YouTube
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, ImageClip, CompositeVideoClip
import cv2
import os
import math
import random



def get_subtitles(video_url):
    video_id = video_url.split('=')[-1]  # Extract video ID from URL
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        subtitles = ''
        for segment in transcript_list:
            subtitles += segment['text'] + ' '
        return subtitles
    except Exception as e:
        print(f"Error fetching subtitles: {e}")
        return None

def text_to_audio(text):
    tts = gTTS(text=text, lang='en')
    audio_stream = BytesIO()
    tts.write_to_fp(audio_stream)
    audio_stream.seek(0)
    audio = AudioSegment.from_file(audio_stream, format="mp3",duration=120)
    return audio

def extract_images(video_url, output_folder='images', num_frames=120):
    try:
        # Download the video using pytube
        yt = YouTube(video_url)
        video_title = yt.title.replace('|', '')
        video_stream = yt.streams.filter(file_extension='mp4').first()
        video_stream.download(output_folder)

        # Use OpenCV to extract frames
        video_path = os.path.join(output_folder, f"{video_title}.mp4")
        video_capture = cv2.VideoCapture(video_path)
        total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))

        # Select random frame indices
        random_frame_indices = random.sample(range(total_frames), num_frames)

        count = 0
        frame_number = 0
        success, image = video_capture.read()
        while success and count < num_frames:
            # Save the frame if it's one of the randomly selected indices
            if frame_number in random_frame_indices:
                image_path = os.path.join(output_folder, f"frame_{count}.jpg")
                cv2.imwrite(image_path, image)
                count += 1
            success, image = video_capture.read()
            frame_number += 1

        print(f"{count} frames extracted successfully.")
    except Exception as e:
        print(f"Error extracting frames: {e}")

@csrf_exempt
def members(request):

    template = loader.get_template('result.html')
    return HttpResponse(template.render())


def youtube_video_processing(request):
    
    video_url = 'https://www.youtube.com/watch?v=YE8yPq6U7SE'
    subtitles = get_subtitles(video_url)

    if subtitles:
        audio = text_to_audio(subtitles)
        audio_path = os.path.join(settings.MEDIA_ROOT, "output_audio.mp3")
        audio.export(audio_path, format="mp3")
        audio_duration = math.ceil(len(audio) / 1000)

        images_folder = 'images'
        extract_images(video_url, output_folder=images_folder, num_frames=120)

        # Create a video from images
        image_files = [os.path.join(images_folder, f"frame_{i}.jpg") for i in range(119)]
        clip_list = [VideoFileClip(file, audio=False).set_duration(1) for file in image_files]

        # Use the last image for the duration of the audio to ensure it lasts the entire video
        last_image_path = os.path.join(images_folder, f"frame_{119}.jpg")
        last_image = ImageClip(last_image_path, duration=len(audio))

        # Combine the video clips into a final video
        final_clip = concatenate_videoclips(clip_list, method="compose").set_audio(audio)

        # Overlay the last image to ensure the video duration matches the audio
        final_clip = CompositeVideoClip([final_clip.set_audio(last_image.audio)])

        # Export the final video
        video_output_path = os.path.join(settings.MEDIA_ROOT, "output_video.mp4")
        final_clip.write_videofile(video_output_path, codec="libx264", audio_codec="aac")

        # Combine video and audio
        title = "Result"
        video_clip = VideoFileClip(video_output_path)
        audio_clip = AudioFileClip(audio_path)
        final_clip = video_clip.set_audio(audio_clip)

        # Export the final video with audio
        final_output_path = os.path.join(settings.MEDIA_ROOT, title + ".mp4")
        final_clip.write_videofile(final_output_path)

        return render(request, 'result.html', {'audio_path': audio_path, 'video_path': final_output_path})
    else:
        return HttpResponse("Failed to fetch subtitles.")
