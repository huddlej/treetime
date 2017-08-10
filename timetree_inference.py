#!/usr/bin/env python

import numpy as np
from .treetime import TreeTime
from Bio import Phylo, AlignIO
from Bio import __version__ as bioversion

if __name__=="__main__":
    ###########################################################################
    ### parameter parsing
    ###########################################################################
    import argparse
    parser = argparse.ArgumentParser(
            description=\
"Reconstructs ancestral sequences and infers a molecular clock tree. The"\
" script produces an alignment file ending on _ancestral.fasta which contains"\
" the inferred ancestral sequences and a tree file ending on _timetree.nexus."\
" Inferred mutations are included as comments. The molecular clock, along with the inferred"\
" GTR model, is written to stdout)")
    parser.add_argument('--aln', required = True, type = str,  help ="fasta file with input sequences")
    parser.add_argument('--tree', required = True, type = str,  help ="newick file with tree")
    parser.add_argument('--dates', required = True, type = str,
                        help ="csv with dates for nodes with 'node_name, date' where date is float (as in 2012.15)")
    parser.add_argument('--infer_gtr', default = True, action='store_true', help='infer substitution model')
    parser.add_argument('--reroot', required = False, type = str, default='best',
                        help ="reroot the tree. Valid arguments are 'best', 'midpoint', or a node name")
    parser.add_argument('--optimize_branch_length', default = False, action='store_true',
                        help="Reoptimize branch length. Note that branch length optimized by treetime are only accurate at short evolutionary distances.")
    parser.add_argument('--keep_polytomies', default = False, action='store_true',
                        help="Don't resolve polytomies using temporal information.")
    parser.add_argument('--relax',nargs='*', default = False,
                        help='use an autocorrelated molecular clock. Prior strength and coupling of parent '
                             'and offspring rates can be specified e.g. as --relax 1.0 0.5')
    parser.add_argument('--max_iter', default = 2, type=int,
                        help='maximal number of iterations the inference cycle is run')
    parser.add_argument('--verbose', default = 1, type=int,
                        help='verbosity of output 0-6')
    parser.add_argument('--Tc', default = "0.0", type=str,
                        help='coalescent time scale -- sensible values are on the order of the average '
                             'hamming distance of contemporaneous sequences. In addition, "opt" '
                             '"skyline" are valid options and estimate a constant coalescent rate'
                             'or a piecewise linear coalescent rate history')
    parser.add_argument('--plot', default = False, action='store_true',
                        help='plot the tree on a time axis and save as pdf')
    params = parser.parse_args()
    if params.relax==[]:
        params.relax=True

    ###########################################################################
    ### PARSING DATES
    ###########################################################################
    with open(params.dates) as date_file:
        dates = {}
        for line in date_file:
            try:
                name, date = line.strip().split(',')[:2]
                dates[name] = float(date)
            except:
                continue

    ###########################################################################
    # PARSING OPTIONS
    ###########################################################################
    try:
        Tc = float(params.Tc)
        if Tc<1e-5:
            Tc = None
    except:
        if params.Tc in ['opt', 'skyline']:
            Tc = params.Tc
        else:
            Tc = None

    ###########################################################################
    ### SET-UP and RUN
    ###########################################################################
    myTree = TreeTime(dates=dates, tree=params.tree,
                       aln=params.aln, gtr='JC69', verbose=params.verbose)
    myTree.run(root=params.reroot, relaxed_clock=params.relax,
               resolve_polytomies=(not params.keep_polytomies),
               Tc=Tc, max_iter=params.max_iter,
               use_input_branch_length = (not params.optimize_branch_length))

    ###########################################################################
    ### OUTPUT and saving of results
    ###########################################################################
    if params.infer_gtr:
        print('\nInferred GTR model:')
        print(myTree.gtr)

    print(myTree.date2dist)

    if Tc=='skyline':
        skyline = myTree.merger_model.skyline_inferred(gen=50)
        print("inferred skyline assuming 50 generations per year:")
        for (x,y) in zip(skyline.x, skyline.y):
            print("%1.3f\t%1.3f"%(x,y))


    base_name = '.'.join(params.aln.split('/')[-1].split('.')[:-1])
    # plot
    if params.plot:
        from .treetime.io import plot_vs_years
        import matplotlib.pyplot as plt
        plt.ion()
        leaf_count = myTree.tree.count_terminals()
        label_func = lambda x: x.name[:20] if (leaf_count<30 & x.is_terminal()) else ''
        branch_label_func = lambda x: (','.join([a+str(pos)+d for a,pos, d in x.mutations[:10]])
                                       +('...' if  len(x.mutations)>10 else '')) if leaf_count<30 else ''
        plot_vs_years(myTree, show_confidence=False, label_func = label_func) #, branch_labels=branch_label_func)
        plt.savefig(base_name+'_tree.pdf')
    else:
        # convert branch length to years (this is implicit in the above plot)
        myTree.branch_length_to_years()

    # decorate tree with inferred mutations
    outaln_name = base_name+'_ancestral.fasta'

    AlignIO.write(myTree.get_reconstructed_alignment(), outaln_name, 'fasta')
    terminal_count = 0
    for n in myTree.tree.find_clades():
        if n.up is None:
            continue
        n.confidence=None
        # due to a bug in older versions of biopython that truncated filenames in nexus export
        # we truncate them by hand and make them unique.
        if n.is_terminal() and len(n.name)>40 and bioversion<"1.69":
            n.name = n.name[:35]+'_%03d'%terminal_count
            terminal_count+=1
        if len(n.mutations):
            n.comment= '&mutations="' + '_'.join([a+str(pos)+d for (a,pos, d) in n.mutations])+'"'

    # write tree to file
    outtree_name = '.'.join(params.tree.split('/')[-1].split('.')[:-1])+'_timetree.nexus'
    Phylo.write(myTree.tree, outtree_name, 'nexus')

