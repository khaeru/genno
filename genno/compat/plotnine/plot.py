import logging
from abc import ABC, abstractmethod
from typing import Hashable, Sequence

import plotnine as p9

log = logging.getLogger(__name__)


class Plot(ABC):
    """Class for plotting using :mod:`plotnine`.

    To use this class:

    1. Create a subclass that overrides :attr:`name`, :attr:`inputs`, and
       :meth:`generate`.

    2. Call :meth:`make_task` to get a tuple (callable, followed by key names) suitable
       for adding to a Computer::

         c.add("foo", P.make_task())
    """

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
        """Return a task :class:`tuple` to add to a Computer."""
        return tuple([cls().save, "config"] + (list(inputs) if inputs else cls.inputs))

    @abstractmethod
    def generate(self, *args, **kwargs):
        """Generate and return the plot.

        Must be implemented by subclasses.
        """
