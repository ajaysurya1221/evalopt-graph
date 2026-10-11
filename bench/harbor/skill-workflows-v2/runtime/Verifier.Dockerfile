ARG RUNTIME_IMAGE
FROM ${RUNTIME_IMAGE}
RUN mkdir -p /candidate-root/workspace /candidate-root/tmp \
    && cp -a /usr /lib /candidate-root/ \
    && if [ -e /lib64 ]; then cp -a /lib64 /candidate-root/; fi \
    && chmod 1777 /candidate-root/tmp
# Controller/hidden cases remain outside this chroot. Candidate imports execute
# as nobody and see only an immutable stopped snapshot and the current input.
