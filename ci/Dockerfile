FROM debian:8 AS base
ENV  DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
  apt-get upgrade && \
  apt-get install --no-install-recommends --no-install-suggests -y \
          gcc \
          git \
          openssh-client \
          make \
          locales \
          python \
          python-dev \
          python-pytango \
          python-virtualenv \
          virtualenv


ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV LANGUAGE=C.UTF-8
# Add user jenkins to the image
RUN groupadd -g 1001 jenkins && \
    useradd -m -u 1001 -g 1001 -d /home/jenkins2 -s /bin/bash jenkins && \
    mkdir /home/jenkins && chown jenkins:jenkins /home/jenkins && \
    echo "jenkins:jenkins" | chpasswd
USER jenkins
RUN virtualenv /home/jenkins/tools2 && \
    git clone https://forge.frm2.tum.de/review/frm2/taco/tools /home/jenkins/tools2src && \
    . /home/jenkins/tools2/bin/activate && \
    pip install -U pip wheel setuptools && \
    pip install /home/jenkins/tools2src/ && \
    rm -rf /home/jenkins/tools2src

RUN virtualenv --system-site-packages /home/jenkins/secopvenv && \
    git clone https://forge.frm2.tum.de/review/sine2020/secop/playground /home/jenkins/playground && \
    . /home/jenkins/secopvenv/bin/activate && \
    pip install -U pip wheel setuptools && \
    pip install -r /home/jenkins/playground/requirements-dev.txt -r /home/jenkins/playground/requirements.txt && \
    rm -rf /home/jenkins/playground


FROM base AS docs
ENV  DEBIAN_FRONTEND=noninteractive

USER root
RUN apt-get update && \
   apt-get install -y --no-install-suggests --no-install-recommends \
     texlive-latex-extra \
     texlive-latex-base \
     texlive-latex-recommended \
     texlive-fonts-recommended \
     texlive-base \
     texlive-binaries \
     latexmk
