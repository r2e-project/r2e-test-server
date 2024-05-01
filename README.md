# R2E Test Server

This is the test server for the [R2E framework](https://github.com/r2e-project). R2E turns any GitHub repository into an executable programming agent environment. More information about the project and framework can be found at our [webpage](https://r2e-project.github.io).


This server provides a [rPyC](https://rpyc.readthedocs.io/en/latest/) (remote Python call) interface to the R2E testing framework. The server is used to execute code and tests for the agent in a pre-built environment for the repository and return the results. More on how this integrates with the R2E framework can be found in the [R2E Repository](https://github.com/r2e-project/r2e).


## Installation

Install the server using [pip](https://pypi.org/project/r2e_test_server/) or any other package manager:

```bash
pip install r2e_test_server
```

## Usage

To start the server, run the following command:

```bash
r2e-test-server start
```

To stop the server, run the following command:

```bash
r2e-test-server stop
```
