FROM alpine:3.20
LABEL maintainer="Brian <bkimmle@gmail.com>"

# Default interval to every hour
ENV TZ=America/Chicago
ENV EXECUTION_CRON_EXPRESSION='0 * * * *'
ENV CONFIG_PATH_FILE='/config/config.conf'
ENV ENABLED_DELETE_WATCHED_TV='1'
ENV ENABLED_MOVE_LIVE_TV='1'
ENV ENABLED_DELETE_OLD_TV='1'

RUN apk update && apk add bash && apk add --no-cache python3 py3-pip py3-requests tzdata && mkdir /app && mkdir /logs && mkdir /etc/cron.d

# Add the scripts 
COPY run-entry.sh /app/run-entry.sh
COPY run-plexcleaner.sh /app/run-plexcleaner.sh
COPY deleteWatchedTv.py /app/deleteWatchedTv.py
COPY moveLiveTv.py /app/moveLiveTv.py
COPY deleteOldTv.py /app/deleteOldTv.py
COPY logrotate.conf /etc/logrotate.d/plexcleaner.conf

RUN chmod 777 /app/run-entry.sh && chmod 777 /app/run-plexcleaner.sh && chmod 777 /app/deleteWatchedTv.py && chmod 777 /app/moveLiveTv.py && chmod 777 /app/deleteOldTv.py && chmod 644 /etc/logrotate.d/plexcleaner.conf && ln -sf /usr/share/zoneinfo/$TZ /etc/localtime

# REQUIRED
# In case the script is configured to directly delete the files, we need to mount the plex data folder
VOLUME ["/media"]
VOLUME ["/config"]
VOLUME ["/logs"]
VOLUME ["/recorded_tv"]

ENTRYPOINT ["/app/run-entry.sh"]
