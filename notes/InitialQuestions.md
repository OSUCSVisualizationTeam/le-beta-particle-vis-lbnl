# Initial questions

## Implementation Specific

- Are there resources or recommended solutions available to support development on a Windows machine—such as access to a virtual machine or cloud-based Mac environment—given that the goal is to create a GUI capable of running on a MacBook Pro?
- How does the lab host the software? Do you have a private or public source code repository?
- What version control system do you use for your software projects? (Git, mercurial, etc)
- Is there macOS GUI in existence today or is part of the focus to develop it from the ground up?
- Given the project description asks for “realtime identification”, we’d like to know more about the data delivery method from the sensor to the data pool. Also how do we access the data pool, are there specific protocols we should use? Is this behind rest APIs or can we gather the data via more real-time-oriented mechanism such as gRPC?
- What is the usual size of samples we will be analyzing?
- Is macOS hardware responsible of analyzing the data locally? Or, is it meant only for visualization?
- Once analyzed a trace and results are produced, is there a repository or database to store results?
- Is the GUI application expected to also display and present historical data?
- Will the GUI application be published as a standalone application (Apple Notarized, outside of the app store)

## From the paper

- How does CCD sensors actually work? From the paper it seems the resulting data is returned in a 10 x 10 grid yet the pictures in the paper make it seem like the elements in the grid are not simple single-color pixels

## Data Analysis

- What are the key performance metrics or success criteria for the particle identification and visualization system?
- What is included in the data that the CCD outputs that we will be examining? Does it come in a specific file format that we could review the standards of or a different collection of files?

  A: From the [project description](https://eecs.engineering.oregonstate.edu/capstone/submission/pages/viewSingleProject.php?id=PqndOkoBofrFEYKd) it seems the data is coming in the form of [NumPy arrays](https://numpy.org/doc/stable/reference/arrays.html).

## Current Capabilities

- What are the current capabilities of the existing system that we will be expanding on for real-time applications? As in what are the current particle identification methods that the system utilizes?

## Miscellaneous

- Is this project expected to produce a research paper? (another)
