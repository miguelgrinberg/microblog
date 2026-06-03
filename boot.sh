#!/bin/bash
# this script is used to boot a Docker container
while true; do
    alembic upgrade head
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo Deploy command failed, retrying in 5 secs...
    sleep 5
done
exec uvicorn microblog:app --host 0.0.0.0 --port 5000 --access-log
