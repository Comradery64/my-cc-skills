FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates jq git sudo docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m runner
WORKDIR /home/runner

RUN LATEST_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/^v//') \
    && curl -o actions-runner.tar.gz -L "https://github.com/actions/runner/releases/download/v${LATEST_VERSION}/actions-runner-linux-x64-${LATEST_VERSION}.tar.gz" \
    && tar xzf actions-runner.tar.gz && rm actions-runner.tar.gz \
    && ./bin/installdependencies.sh

COPY entrypoint.sh /home/runner/entrypoint.sh
RUN chmod +x /home/runner/entrypoint.sh && chown -R runner:runner /home/runner

USER runner
ENTRYPOINT ["/home/runner/entrypoint.sh"]
