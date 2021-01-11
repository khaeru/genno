def collapse_message_cols(df, var, kind=None):
    """:meth:`as_pyam` `collapse=...` callback for MESSAGE quantities.

    Parameters
    ----------
    var : str
        Name for 'variable' column.
    kind : None or 'ene' or 'emi', optional
        Determines which other columns are combined into the 'region' and
        'variable' columns:

        - 'ene': 'variable' is
          ``'<var>|<level>|<commodity>|<technology>|<mode>'`` and 'region' is
          ``'<region>|<node_dest>'`` (if `var='out'`) or
          ``'<region>|<node_origin>'`` (if `'var='in'`).
        - 'emi': 'variable' is ``'<var>|<emission>|<technology>|<mode>'``.
        - Otherwise: 'variable' is ``'<var>|<technology>'``.

        The referenced columns are also dropped, so it is not necessary to
        provide the `drop` argument of :meth:`as_pyam`.
    """
    if kind == "ene":
        # Region column
        rcol = "nd" if var == "out" else "no"
        df["region"] = df["region"].str.cat(df[rcol], sep="|")
        df.drop(rcol, axis=1, inplace=True)

        var_cols = ["l", "c", "t", "m"]
    elif kind == "emi":
        var_cols = ["e", "t", "m"]
    else:
        var_cols = ["t"]

    # Assemble variable column
    df["variable"] = var
    df["variable"] = df["variable"].str.cat([df[c] for c in var_cols], sep="|")

    # Drop same columns
    return df.drop(var_cols, axis=1)
