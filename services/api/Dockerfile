FROM python:3.11-slim
# Jenkins passes the semver version in with --build-arg APP_VERSION=x.y.z
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}
RUN useradd -r -u 1001 clearops
WORKDIR /app
COPY app.py .
RUN chown clearops /app/app.py
USER clearops
EXPOSE 8080
CMD ["python3", "app.py"]
