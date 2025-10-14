# Kickoff Meeting Summary: CCD Radiation Detector Project

---

## 1. Project Background and Technology

* The project is run by the Applied Nuclear Physics group at Berkeley Lab and focuses on using **Charge-Coupled Devices (CCDs)** as highly sensitive **radiation detectors**.
* CCDs, originally designed for astronomy, work by measuring the charge liberated when light or high-energy ionizing radiation interacts with the silicon chip.
* The raw data is a **matrix of charge values** (an image), and different radiation types leave distinct **patterns, or "clusters,"**.
    * **Muons** create straight tracks.
    * **Gamma rays** cause Compton scattering, producing **Compton electrons** that leave squiggly tracks.
    * **Alpha particles** deposit a large amount of charge in a high-intensity circular pattern.
* A key physical phenomenon is that charge produced deeper in the sensor spreads out more as it drifts to the surface pixels, affecting the final cluster shape.
* The raw data is stored in the astronomy format **FITS (.FITS)**.

---

## 2. Specific Application: Tritium Detection

* The core application is the detection of **tritium**, a radioactive isotope of hydrogen with a very **low-energy beta decay** (maximum of $18 \text{ keV}$).
* Tritium is difficult to detect and a marker for nuclear activity.
* Previous project work centered on using **deep learning/machine learning** for better **classification** to distinguish the true tritium signals (small, spread-out clusters) from low-energy background events.
* The main method of differentiation is the **cluster width/shape**, as tritium interacts right at the sensor surface, causing maximum charge spread by the time the charge reaches the pixels.

---

## 3. Project Goal and Deliverable

The previous work is a **proof-of-concept prototype**. The main goal for this team is to take the next step by formalizing the computing workflow and developing a **live, interactive software framework** for the new experimental CCD test stand.

### Initial Objective: Interactive GUI and Data Workflow

The primary deliverable is a **Graphical User Interface (GUI)** and analysis framework that runs live next to the hardware. It should be able to:

* **Process Raw Data:** Take the raw FITS exposure data, perform **segmentation** (cutting the image into clusters), and run basic classification on each cluster.
* **Visualize Events:** Allow users to easily **browse and filter** the event displays (clusters).
* **Filtering:** Enable sorting and filtering of clusters by **type** (e.g., muon, tritium candidate), **energy**, or **number of pixels**.
* **Historical Analysis:** Support the display of historical data and allow users to run simple analyses, such as plotting data or finding all events of a certain type from the last several weeks. The system is expected to run 24/7.

### Potential Future Avenues

* Further development and refinement of the existing **tritium classification** algorithms.
* Developing a machine learning task to estimate the **direction of origin** for particles like Compton electrons.
