# Third Meeting Summary

This meeting covered a range of topics related to the beta particle track visualization project, from low-level data processing to high-level architecture and project management.

## Key Discussion Points:

### 1. Data Processing & Clustering
- **Thresholding:** The team discussed using a 3-sigma threshold based on standard deviation for noise filtering. This provides a balance between removing noise and preserving faint particle tracks.
- **Processing Modes:** A key architectural decision was made to support two distinct processing modes:
    - **Offline Batch Mode:** Prioritizes accuracy and precision for generating final results.
    - **Online Interactive Mode:** Prioritizes speed for real-time user analysis, where a human operator can "play" with the data. HDBSCAN is being explored for this mode.
- **Clustering Approach:** The group agreed to use a "classical" connected-components algorithm for initial cluster segmentation, finding it more reliable than ML-based segmentation. Machine learning will be used for the *classification* of these found clusters, not for the segmentation itself.
- **Intermediate Data Format:** To speed up analysis, the team is considering an intermediate data format that stores pre-processed cluster data (e.g., energy, position), avoiding the need to re-run heavy computations on raw images.

### 2. Code, Repository, and Data Management
- **Code Repository:** The team will consolidate their work, likely in the GitLab repository provided, to ensure everyone has access.
- **Storing Results:** A proposal was made to store cluster analysis results directly within the FITS file headers. While this enhances portability, concerns about header size limitations were raised. A companion file (e.g., a pickle file) was suggested as a viable alternative.

### 3. Machine Learning & CNN
- **CNN Integration:** The team reviewed the existing `MLCCD` repository and its tritium recognition CNN. They will adapt their data pipeline to match the data format used in this repo to leverage the existing models.
- **Trained Models:** The lab team will provide the student team with pre-trained Keras model files, so they will not need to perform the model training themselves.
- **Hardware (CUDA):** While some notebooks contained CUDA references, it was clarified that GPUs are primarily for training. The core application for inference and analysis will not require NVIDIA hardware, ensuring it can run on standard machines like macOS laptops.

### 4. Project Management & Next Steps
- **Design Document:** The student team is preparing a design document, due December 1st, which will outline the project's architecture and data flows.
- **Follow-up Meeting:** A meeting is scheduled for the following Monday morning to review the consolidated design and plan.

This summary was generated using Google's Gemini AI
