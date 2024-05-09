# FROM condaforge/miniforge3:latest

# ENV ENV_FILE "environment.yml"

# RUN conda update -n base -c conda-forge mamba

# COPY ${ENV_FILE} /config/vapack/${ENV_FILE}
# RUN mamba env update -n base --file /config/vapack/${ENV_FILE}

# ENTRYPOINT [ "bash" ]

FROM ubuntu:22.04

ENV MINIFORGE_VER "24.1.2-0"
ENV MINIFORGE_INSTALL_FILE "Mambaforge-${MINIFORGE_VER}-Linux-x86_64.sh"
ENV MINIFORGE_DL_LINK "https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VER}/${MINIFORGE_INSTALL_FILE}"
ENV ENV_FILE "environment.yml"

RUN apt-get update && apt-get install sharutils -y

RUN mkdir /downloads
ADD ${MINIFORGE_DL_LINK} /downloads
ADD ${MINIFORGE_DL_LINK}.sha256 /downloads

WORKDIR /downloads
RUN test -f ${MINIFORGE_INSTALL_FILE}.sha256
RUN sha256sum --quiet -c ${MINIFORGE_INSTALL_FILE}.sha256
RUN bash ${MINIFORGE_INSTALL_FILE} -b

# COPY ${ENV_FILE} /config/vapack/${ENV_FILE}
# RUN bash mamba env update -n base --file /config/vapack/${ENV_FILE}

ENTRYPOINT [ "bash" ]
