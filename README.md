# Visualization and Discernment of Low-Energy Beta Particle Tracks from Live CCD Detector Data

Building on exisiting deep learning research from Lawrence Berkeley
National Laboratory (LBNL), this project addresses the logistical
challenges of traditional radiation detection. The core goal is to
create an interactive visual analysis tool that empowers scientists to
accelerate discovery and improve machine learning (ML) models. The
system will provide a Graphical User Interface (GUI) to directly
explore, filter, and experiment with raw Charge-Coupled Device (CCD)
data. This visual-first approach facilitates the insights needed to
design and refine more effective ML classifiers for particle
interactions. While the initial focus is on enhancing tritium detection,
the solution is fundamentally a flexible discovery platform, designed to
uncover a broad range of phenomena hidden within the data and bridge the
gap between research and a real-time, portable detection system.

## Team Documentation and Research

- Pre [kickoff questions](notes/InitialQuestions.md)
- See [Notes here](notes/README.md)
- Knowledgebase is [located here](research/README.md)

## OSU Capstone Project Description

### Objectives

The goal for this project would be a graphical user interface that's capable of running on a Macbook Pro. The program will employ machine vision techniques and machine learning to be able to classify particle tracks found in CCD exposures in the form of numpy arrays or other image formats. The program will feature various ways of displaying particle tracks in the image by type, with options for labels, filtering by type, energy, vector, or any other attribute which can be ascertained in software. The project is somewhat open-ended, and the resulting product will depend on the creativity and resourcefulness of the student.

### Motivations

This project would enhance the capabilities of the existing system by extending its utility for real-time applications. The ability to visualize multiple particle types in real-time, and provide insight into the detection results would offer significant utility in a range of nuclear safety and security use cases.

### References

FITS files and relevant cited functionality were provided by the Applied Nuclear Physics program at the Lawrence Berkeley National Laboratory.

## Directory Structure

The project follows a "src-layout" to separate product code from research artifacts.

- `src/le_beta_vis/`: The main source code for the application.
    - `common/`: Shared logic and data models (e.g., `CCDCaptureModel`) used by both Backend and Frontend.
    - `backend/`: The Unattended Ingress & Processing Pipeline services.
    - `frontend/`: The PySide6 Desktop GUI Application.
- `experiments/`: Research scratchpads and prototyping scripts.
- `cluster_demonstration/`: Jupyter notebooks for algorithm demonstrations.
- `design/`: Design documents and assets.
- `environment.yml`: The consolidated Conda environment file for the project.
