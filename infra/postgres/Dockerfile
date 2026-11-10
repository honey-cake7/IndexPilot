FROM postgres:18.6-bookworm@sha256:f1ea2a1a4fb7b68d4836be1fdcb8a6466a89b072158bf9d97663600538c294c5 AS builder
ARG HYPOPG_REVISION=21d5461ad1868434cc47d9aa656d7afc2b24c464
ARG HYPOPG_SHA256=a57c34a0e2752176a1ba3d3b990cffe8ed8d65fccda96052a7f5605c274f554f
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates curl postgresql-server-dev-18 \
    && curl -fsSL "https://codeload.github.com/HypoPG/hypopg/tar.gz/${HYPOPG_REVISION}" -o /tmp/hypopg.tar.gz \
    && echo "${HYPOPG_SHA256}  /tmp/hypopg.tar.gz" | sha256sum -c - \
    && mkdir /tmp/hypopg \
    && tar -xzf /tmp/hypopg.tar.gz -C /tmp/hypopg --strip-components=1 \
    && make -C /tmp/hypopg \
    && make -C /tmp/hypopg install DESTDIR=/opt/hypopg

FROM postgres:18.6-bookworm@sha256:f1ea2a1a4fb7b68d4836be1fdcb8a6466a89b072158bf9d97663600538c294c5
COPY --from=builder /opt/hypopg/ /
COPY infra/postgres/init.sh /docker-entrypoint-initdb.d/10-indexpilot.sh
COPY --chmod=0755 infra/postgres/entrypoint.sh /usr/local/bin/indexpilot-entrypoint.sh
ENTRYPOINT ["indexpilot-entrypoint.sh"]
CMD ["postgres"]
