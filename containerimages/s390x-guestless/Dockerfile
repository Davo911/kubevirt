FROM s390x/fedora:40

RUN dnf install -y python3 busybox cpio
COPY make-tiny-image.py /usr/local/bin/make-tiny-image.py
RUN chmod +x /usr/local/bin/make-tiny-image.py
RUN make-tiny-image.py --output /tiny-initrd.img --run "poweroff -f"
