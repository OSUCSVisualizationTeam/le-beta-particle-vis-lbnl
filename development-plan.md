# Visualization and Discernment of Low-Energy Beta Particle Tracks from Live CCD Detector Data

## Major Project Milestones

### Final ("Alpha")
*   **What is the overall project goal for this deliverable?**
    *   To release a fully integrated Minimum Viable Product (MVP) that automates the ingestion and classification of CCD data while simultaneously providing scientists with a high-fidelity, interactive GUI for verifying results and exploring raw data in real-time.
*   **This is your Minimum Viable Product (MVP). What features will it have?**
    *   **Unattended Pipeline:** Automatic detection, ingestion, segmentation, and classification of new FITS files.
    *   **Event Persistence:** A structured MySQL database storing file metadata, cluster properties, and classification results.
    *   **Configuration Management:** A centralized service (Redis + File) managing all system paths and parameters.
    *   **Interactive Raw Data Analysis:** A GUI capability to load raw FITS files, view HDU mosaics, and inspect pixels with basic HDR rendering.
    *   **Historical Event Analysis:** A "Live Mode" dashboard that queries the database to display classified events as they are processed.
    *   **Results Export:** Ability to export event lists to CSV and plots to image files.
*   **What will not be included? Include any major deviations from the original Requirements or Design.**
    *   **Advanced Model Retraining Interface:** While the *API* for curation will be built, the actual GUI for retraining the model on the fly is out of scope for Alpha.
    *   **Cloud/Remote Deployment:** The Alpha will be designed for local execution (client and server on the same machine or LAN).
    *   **User Authentication:** The system will assume a secure lab environment; no login/RBAC will be implemented for Alpha.
    *   **Complex Custom Filtering:** Only the base filter stack (Pedestal, Gaussian) will be implemented; advanced custom filters will be deferred.
*   **Which major Requirements/Stories/Use-cases/Tasks will be satisfied this term?**
    *   Functional Area 1: Interactive Raw Data Analysis Application
    *   Functional Area 2: Historical Event Analysis Application
    *   Functional Area 3: Results Export & Reporting
    *   Functional Area 4: Unattended Ingress & Processing Pipeline
    *   Functional Area 5: Event Persistence Service
    *   Functional Area 6: Configuration Management

---

## Overall Sprint Plan

### Sprint 1: Foundation & Independent Verticals
*   **Sprint Goal:** Establish the "Source of Truth" (Configuration), the "Data Contract" (Database), and the "Visual Canvas" (FITS Loading) to enable independent development of the frontend and backend.
*   **High-level tasks:**
    *   **Nicholas (Config):** Implement the Configuration Service and Python SDK using Redis (for cache) and local files (for persistence). Define the `global`, `pipeline`, and `gui` namespaces.
    *   **Troy (Backend):** Design and deploy the MySQL Database Schema (`fits_files`, `clusters`). Implement the Unattended Ingress File Watcher to detect and log new files.
    *   **Juan (Frontend):** Initialize the Main Window GUI shell. Implement the `CCDCaptureModel` using AstroPy to parse multi-HDU FITS files and display the "Mosaic View" strip.

### Sprint 2: Processing Logic & Data Visualization
*   **Sprint Goal:** Activate the core data processing logic so the pipeline generates results, and implement the primary visualization interfaces to render that data.
*   **High-level tasks:**
    *   **Troy (Backend):** Implement the "Classical Connected Components" segmentation algorithm and integrate the Keras ML Model for classification. Ensure the database populates with live results.
    *   **Juan (Frontend):** Develop the core Raw Image View using OpenCV-to-QPixmap rendering (with Zoom/Pan). Build the Historical Query Interface (grid view/sidebar) to display database results.
    *   **Nicholas (Support):** Implement the Async Worker Thread infrastructure to prevent GUI freezing. Build the shared Visualization Utility for rendering thumbnails in the History view.

### Sprint 3: Integration, Real-Time Loop & Curation
*   **Sprint Goal:** Connect the backend signals to the frontend for "Live Mode," enable data curation/export, and perform end-to-end system verification.
*   **High-level tasks:**
    *   **Troy (Backend):** Implement the Model Curation API (receiving specific Cluster IDs for retraining) and the Redis "Completion Signal" to notify the GUI of new data.
    *   **Juan (Frontend):** Implement "Live Monitoring Mode" (listening to Redis signals to auto-refresh). Build the Results Export Service (CSV/PNG generation).
    *   **Nicholas (Support):** Build the UI controls (sliders/toggles) for the Interactive Filter Stack. Conduct Integration Testing to verify configuration changes propagate to both pipeline and GUI.
