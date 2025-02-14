import matplotlib.pyplot as plt
import logomaker
import numpy as np
from ..settings.layout_finder import best_layout
from textwrap import wrap
import pandas as pd
import warnings
from iglabel import IMGT

class PrepareData:
    @staticmethod
    def check_args(samples, report, chosen_seq_length,):
        assert type(samples) == list, "You have to give a list as input for the sample"

        if chosen_seq_length != None:
            assert (
                type(chosen_seq_length) == int
            ), "You have to give an integer as input for the sequence length you want to analyze"
        for sample in samples:
            assert (
                sample in report["Experiment"].unique().tolist()
            ), "The provided sample name is not in your sequencing report. Please check the spelling or use the print_samples function to see the names of your samples"

        
    @staticmethod
    def calculate_entropy(probs):
        """Calculate Shannon entropy."""
        return -np.sum(
            [p * np.log2(p) if p > 0 else 0 for p in probs]
        )  # https://biology.stackexchange.com/questions/64368/how-to-determine-the-height-bits-in-a-sequence-logo

    @staticmethod
    def get_labels(region_string:str, chosen_seq_length:int):
        """Creates the IMGT labels for the chosen sequence length

        Args:
            region_string (str): _description_
            chosen_seq_length (int): _description_

        Returns:
            list: A list with strings of either the IMGT labels or the position numbers
        """
        if region_string != "targetSequences":
            region = [region_string.replace("aaSeq", "")]
            label_dict, _ = IMGT([chosen_seq_length * "A"], region, save = False)
            numbers_true = list(label_dict.values())[0]
        else:
            numbers_true = [str(i) for i in list(range(1, chosen_seq_length + 1))]
        return numbers_true

    def cleaning(self, samples, report, chosen_seq_length, region_string, method):
        self.check_args(samples, report, chosen_seq_length)
        local_report = report.loc[report["Experiment"].isin(samples)]
       # sample = report[report["Experiment"] == sample_name]
        local_report = local_report[["Experiment", "cloneFraction", region_string]]
        sequences = local_report[region_string]
        if chosen_seq_length != None:
            assert sequences.str.len().max() >= chosen_seq_length, "Your chosen seq length must exist in your sequence repertoire"
        aminoacids = "ACDEFGHIKLMNPQRSTVWY"

        if chosen_seq_length != None:
            sequences = local_report[
                local_report[region_string].astype(str).str.len() == chosen_seq_length
            ][region_string]
        else:
            warnings.warn(
                "You will no have all sequence length included but the problem of that is that you assume that sequences with different lengths have the same properties on relative amino acid positions, which is not necessarily true."
            )
            sequences = local_report[region_string]
            chosen_seq_length = int(sequences.str.len().max())
            
        compDict = {aa: chosen_seq_length * [0] for aa in aminoacids}
        length_filtered_seqs = sequences.shape[0]
        for seq in sequences:
            for aa_position in range(len(seq)):
                aminoacid = seq[aa_position]
                if aminoacid == "*" or aminoacid == "_":
                    pass
                else:
                    compDict[aminoacid][aa_position] += 1
        if method == "bits":
            # Calculate frequencies
            frequencies = {
                aa: [count / length_filtered_seqs for count in compDict[aa]]
                for aa in aminoacids
            }

            # Calculate Shannon entropy for each position
            entropies = [
                self.calculate_entropy([frequencies[aa][i] for aa in aminoacids])
                for i in range(chosen_seq_length)
            ]

            # Calculate bits for sequence logo for each amino acid
            bits_dict = {
                aa: [
                    2 - entropies[i] if frequencies[aa][i] > 0 else 0
                    for i in range(chosen_seq_length)
                ]
                for aa in aminoacids
            }
            aa_distribution = pd.DataFrame.from_dict(bits_dict)
        else:
            aa_distribution = pd.DataFrame.from_dict(compDict)
            aa_distribution = aa_distribution.divide(
                aa_distribution.sum(axis=1), axis=0
            )
            aa_distribution.astype("float16")
        return aa_distribution


class LogoPlot:
    def __init__(
        self,
        ax,
        sequencing_report,
        region_string,
        sample,
        highlight_spec_position,
        font_settings,
        chosen_seq_length,
        method,
        color_scheme,
        avail_regions,
        **kwargs,
    ):
        self.avail_regions = avail_regions
        self.region_string = region_string
        self.ax = ax
        self.chosen_seq_length = self.find_seq_length(
            sequencing_report, sample, chosen_seq_length, region_string
        )
        self.aa_distribution = PrepareData().cleaning(
            sample, sequencing_report, self.chosen_seq_length, region_string, method
        )
        # self.createPlot()
        self.font_settings = font_settings
        self.func_type = {
            "alpha": [0.01, 0.01, 0.01, 1],
            "shade": [0.01, 0.01, 0.01, 1],
            "fade": [0.01, 0.01, 0.01, 1],
        }
        self.button_type = {
            "alpha": "CustomScale",
            "shade": "CustomScale",
            "fade": "CustomScale",
        }
        self.createPlot(color_scheme=color_scheme, **kwargs)
        self.add_style(highlight_spec_position, sample)

    @staticmethod
    def find_seq_length(
        sequencing_report, sample, chosen_seq_length, region_of_interest
    ):
        filtered_data = sequencing_report.loc[sequencing_report["Experiment"].isin(sample)]
        length_counts = filtered_data[region_of_interest].str.len().value_counts()

        if chosen_seq_length == None:
            max_length = length_counts.idxmax()
            chosen_seq_length = max_length
        else:
            if chosen_seq_length in length_counts:
                pass
            else:
                print(
                    "The chosen sequence length is not in the data. The most frequent sequence length was chosen instead"
                )
                max_length = length_counts.idxmax()
                chosen_seq_length = max_length
            
        return int(chosen_seq_length)

    def createPlot(
        self,
        shade_below=0.5,
        fade_below=0.5,
        font_name="Arial Rounded MT Bold",
        color_scheme="skylign_protein",
        show_spines=False,
    ):

        self.logo_plot = logomaker.Logo(
            self.aa_distribution,
            shade_below=shade_below,
            fade_below=fade_below,
            font_name=font_name,
            color_scheme=color_scheme,
            show_spines=show_spines,
            ax=self.ax,
        )
        self.logo_plot.style_xticks(anchor=1, spacing=1, rotation=0)

            
    def add_style(self, highlight_specific_pos, sample):
        if "fontsize" in self.font_settings.keys():
            original_fontsize = self.font_settings["fontsize"]
            self.ax.set_ylabel("Frequency", **self.font_settings)
            self.ax.set_xlabel("Position on sequence", **self.font_settings)
            self.font_settings["fontsize"] = 22
            title = "\n".join(
                wrap(
                    "Logo Plot of "
                    + " ".join(sample)
                    + " with sequence length "
                    + str(self.chosen_seq_length),
                    width=40,
                )
            )
            plt.title(title, **self.font_settings)
            self.font_settings["fontsize"] = original_fontsize
            labels_true = list(range(0, self.chosen_seq_length))
            if self.region_string != "targetSequences":
                region = [self.region_string.replace("aaSeq", "")]
                label_dict, _ = IMGT([self.chosen_seq_length * "A"], region, save = False)
                numbers_true = list(label_dict.values())[0]
            else:
                numbers_true = list(range(1, self.chosen_seq_length + 1))
            assert len(numbers_true) == len(labels_true), f" you have {len(numbers_true)} labels and {len(labels_true)} and xticsk"
            plt.xticks(labels_true, numbers_true)
            if highlight_specific_pos != None:
                self.logo_plot.highlight_position(p=5, color="gold", alpha=0.5)


def plot_logo_multi(
    fig,
    sequencing_report,
    samples,
    font_settings,
    region_string,
    method,
    chosen_seq_length=16,
):
    if samples == "all":
        unique_experiments = sequencing_report["Experiment"].unique()
        unique_experiments = np.sort(unique_experiments)
    else:
        unique_experiments = sequencing_report["Experiment"].unique()
        unique_experiments = np.array([i for i in unique_experiments if i in samples])
        unique_experiments = np.sort(unique_experiments)
    Tot = unique_experiments.shape[0]
    Rows, Cols = best_layout(Tot)
    Position = range(1, Tot + 1)
    n = 0
    adapted_fontsize = 10 - int(Cols) + 2
    original_fontsize = font_settings["fontsize"]
    font_settings["fontsize"] = adapted_fontsize
    #  fig = plt.figure(1, constrained_layout=True)
    for i in unique_experiments:
        aa_distribution = PrepareData().cleaning(
            [i], sequencing_report, chosen_seq_length, region_string, method
        )
        if aa_distribution.isna().any().any():
            continue

        ax = fig.add_subplot(
            Rows, Cols, Position[n], xticks=(np.arange(0, chosen_seq_length, step=1))
        )
        logo_plot = logomaker.Logo(
            aa_distribution,
            shade_below=0.5,
            fade_below=0.5,
            font_name="Arial Rounded MT Bold",
            color_scheme="skylign_protein",
            show_spines=False,
            ax=ax,
            allow_nan=True,
        )
        # logo_plot.set_xticks(range(aa_distribution.shape[0]))
        logo_plot.style_xticks(
            anchor=0,
            spacing=1,
            rotation=0,
        )
        plt.title(
            i, **font_settings
        )  # check out https://matplotlib.org/3.1.0/api/_as_gen/matplotlib.pyplot.title.html

        n = n + 1
    else:
        print("Sample " + i + "was skipped because no sequence was found")
    original_fontsize = font_settings["fontsize"]
    font_settings["fontsize"] = 22
    fig.suptitle(
        "Logo Plots for sequence Length " + str(chosen_seq_length), **font_settings
    )
    font_settings["fontsize"] = original_fontsize
