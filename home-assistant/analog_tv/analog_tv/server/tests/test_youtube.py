from analog_tv.integrations.youtube import YouTubeClient

def test_youtube_duration_parser():
    assert YouTubeClient.parse_duration("PT1H2M3S") == 3723
    assert YouTubeClient.parse_duration("PT12M") == 720
