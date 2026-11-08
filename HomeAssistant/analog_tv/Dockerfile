FROM ghcr.io/home-assistant/base:latest
RUN apk add --no-cache python3 py3-pip ffmpeg bash tzdata ca-certificates
WORKDIR /opt/analog_tv
COPY server/ /opt/analog_tv/
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
