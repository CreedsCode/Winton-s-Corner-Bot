FROM postgres:17-alpine
RUN apk add --no-cache git build-base clang16 llvm16 postgresql17-dev \
    && git clone https://github.com/michelp/pgjwt.git /tmp/pgjwt \
    && cd /tmp/pgjwt && make install \
    && rm -rf /tmp/pgjwt
