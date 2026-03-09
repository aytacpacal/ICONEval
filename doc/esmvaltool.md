[Back to README](../README.md)

# ESMValTool

ICONEval is based on ESMValTool, a "community diagnostic and performance
metrics tool for routine evaluation of Earth system models in CMIP".
Originally, ESMValTool has been designed to compare long (> 30 years) climate
simulations from multiple models with each other and/or with observational
references (like in-situ data, satellite data, reanalyses, etc.). Recently, the
capacity to read native model output of some specific models was added (see
[here](https://gmd.copernicus.org/articles/16/315/2023/) for more details). The
term "native model output" refers to the operational output that is produced by
running a climate model through the standard workflow of the corresponding
modeling institute (details). One of these models is ICON.

A general tutorial on ESMValTool is available
[here](https://tutorial.esmvaltool.org/). This covers the basic elements of the
tool, but not yet how to read native model output. Details on reading ICON data
with ESMValTool are given
[here](https://docs.esmvaltool.org/projects/ESMValCore/en/latest/quickstart/find_data.html#icon).

To ensure a smooth evaluation of ICON output with ICONEval/ESMValTool, please
ensure that the ICON output follows the conventions and standards described
[here](doc/icon_output_format.md). If you encounter any problems, please have a
look at the [FAQs](doc/faqs.md).
