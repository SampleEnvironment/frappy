FROM python:3.9 AS base
ARG PYVER=python3
ENV  DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
  apt-get upgrade -y && \
  apt-get install --no-install-recommends --no-install-suggests -y \
          gcc \
          git \
          openssh-client \
          make \
          locales \
          python3 \
          python3-dev \
          python3-venv python3-setuptools \
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

RUN virtualenv -p /usr/bin/python3 --system-site-packages /home/jenkins/secopvenv && \
    git clone https://forge.frm2.tum.de/review/secop/frappy /home/jenkins/frappy && \
    . /home/jenkins/secopvenv/bin/activate && \
    pip install -U pip wheel setuptools importlib_metadata && \
    pip install -r /home/jenkins/frappy/requirements-dev.txt -r /home/jenkins/frappy/requirements.txt pylint pytest && \
    rm -rf /home/jenkins/frappy


FROM base AS docs
ARG PYVER=python3
ENV  DEBIAN_FRONTEND=noninteractive

USER root
RUN apt-get update && \
   apt-get install -y --no-install-suggests --no-install-recommends \
     texlive-latex-extra \
     texlive-latex-base \
     texlive-latex-recommended \
     texlive-fonts-recommended \
     texlive-fonts-extra \
     tex-gyre \
     texlive-base \
     texlive-binaries \
     latexmk
