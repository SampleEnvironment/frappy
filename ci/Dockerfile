FROM debian:8 AS base
ENV  DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
  apt-get upgrade && \
  apt-get install --no-install-recommends --no-install-suggests -y \
          gcc \
          git \
          openssh-client \
          make \
          python \
          python-dev \
          python-virtualenv \
          virtualenv


ENV LC_ALL=C.utf8
ENV LANG=C.utf8
ENV LANGUAGE=C.utf8
# Add user jenkins to the image
RUN groupadd -g 1001 jenkins && \
    useradd -m -u 1001 -g 1001 -d /home/jenkins2 -s /bin/bash jenkins && \
    mkdir /home/jenkins && chown jenkins:jenkins /home/jenkins && \
    echo "jenkins:jenkins" | chpasswd
USER jenkins
RUN virtualenv /home/jenkins/secopvenv

FROM base AS docs
ENV  DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
   apt-get install -y --no-install-suggests --no-install-recommends \
     texlive-latex-extra \
     texlive-latex-base \
     texlive-latex-recommended \
     texlive-base \
     texlive-binaries

