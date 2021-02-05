import logging
from abc import ABC, abstractmethod
from typing import Hashable, Sequence

import plotnine as p9

log = logging.getLogger(__name__)


class Plot(ABC):
    """Class for plotting using :mod:`plotnine`."""

    #: Filename base for saving the plot.
    basename = ""
    #: File extension; determines file format.
    suffix = ".pdf"
    #: Keys for quantities needed by :meth:`generate`.
    inputs: Sequence[Hashable] = []
    #: Keyword arguments for :meth:`plotnine.ggplot.save`.
    save_args = dict(verbose=False)

    # TODO add static geoms automatically in generate()
    __static: Sequence = []

    def save(self, config, *args, **kwargs):
        path = config["output_dir"] / f"{self.basename}{self.suffix}"

        log.info(f"Save to {path}")

        args = map(lambda qty: qty.to_series().rename(qty.name).reset_index(), args)

        plot_or_plots = self.generate(*args, **kwargs)

        try:
            # Single plot
            plot_or_plots.save(path, **self.save_args)
        except AttributeError:
            # Iterator containing multiple plots
            p9.save_as_pdf_pages(plot_or_plots, path, **self.save_args)

        return path

    @classmethod
    def make_task(cls, *inputs):
        """Return a task :class:`tuple` to add to a Computer.

        Parameters
        ----------
        inputs : sequence of :class:`.Key`, :class:`str`, or other hashable, optional
            If provided, overrides the :attr:`inputs` property of the class.

        Returns
        -------
        tuple
            - The first, callable element of the task is :meth:`save`.
            - The second element is ``"config"``, to access the configuration of the
              Computer.
            - The third and following elements are the `inputs`.
        """
        return tuple([cls().save, "config"] + (list(inputs) if inputs else cls.inputs))

    @abstractmethod
    def generate(self, *args, **kwargs):
        """Generate and return the plot.

        Must be implemented by subclasses.

        Parameters
        ----------
        args : sequence of :class:`pandas.DataFrame`
            Because :mod:`plotnine` operates on pandas data structures, :obj:`Quantity`
            are automatically converted before being provided to :meth:`generate`.
        """
