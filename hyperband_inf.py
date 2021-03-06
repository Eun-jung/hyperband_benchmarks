import time
import numpy
import pickle
import os
import sys, getopt

class Logger(object):
    def __init__(self,dir):
        self.terminal = sys.stdout
        self.log = open(dir+"/hyperband_run.log", "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

def sha_inf(model,params,units,dir,n,B,eta=2,calculate=True):
    def log_eta(x):
        return numpy.log(x)/numpy.log(eta)
    halvings = max(1,int(numpy.ceil(log_eta(n))))

    if calculate:
        arms = model.generate_arms(n,dir,params,max_iter=B/halvings/eta)
        remaining_arms=[list(a) for a in zip(arms.keys(),[0]*len(arms.keys()),[0]*len(arms.keys()),[0]*len(arms.keys()))]
    for i in range(halvings):
        n_arms = int(n/eta**i)
        b_arm = int(B/n_arms/halvings)
        print '%d\t%d' %(n_arms,b_arm)
        if calculate:
            for a in range(len(remaining_arms)):
                start_time=time.time()
                arm_key=remaining_arms[a][0]
                train_loss,val_acc, test_acc=model.run_solver(units,b_arm,arms[arm_key])
                print arm_key, train_loss, val_acc, test_acc, (time.time()-start_time)/60.0
                arms[arm_key]['results'].append([b_arm,train_loss,val_acc,test_acc])
                remaining_arms[a][1]=train_loss
                remaining_arms[a][2]=val_acc
                remaining_arms[a][3]=test_acc
            remaining_arms=sorted(remaining_arms,key=lambda a: -a[2])[0:max(1,int(numpy.ceil(n_arms/eta)))]
    if calculate:
        best_arm=arms[remaining_arms[0][0]]
        return arms,[best_arm,remaining_arms[0][1],remaining_arms[0][2],remaining_arms[0][3]]
    else:
        return None, None


def hyperband_inf(model,runtime,units,dir,params,eta,max_k=3, starting_b=1,min_unit=1,min_arms=1,max_unit=None,calculate=True):
    # inputs:
    # model - object with necessary subroutines to generate arms and train models
    # runtime - total time to run the optimization routine
    # units - type of resource that will be allocated choices are "iter" or "time."  iter should be used for everything if
    #         time is not the desired resource
    # dir - output directory to store the files for this run
    # params - object with specified hyperparameter search space from which arms are sampled
    # eta - elimination rate
    # max_k - # of times to run hyperband, i.e. # of times to repeat the outer loops over the tradeoffs s
    # starting_b - starting budget for each bracket.  Each outer loop of infinite horizon hyperband doubles this budget
    #              by a factor of 2.
    # min_units - minimum units to train any configuration on
    # min_arms - option to set a minimum # of arms so that any bracket that tries fewer than min_arms is excluded from
    #            the run.
    # max_units - not required, optional input in case a max_unit is desired
    # calculate - flag to skip calculation if desired to see the allocation scheme with the inputed parameters

    t_0 = time.time()
    print time.localtime(t_0)
    def log_eta(x):
        return numpy.log(x)/numpy.log(eta)
    def minutes(t):
        return (t-t_0)/60.
    k=0
    best_acc=0
    results_dict={}
    time_test=[]
    while minutes(time.time())< runtime and k <max_k:
        l=0
        B=starting_b*2**k
        while int(log_eta(B))-l > log_eta(l):
            l+=1
        l=max(0,l-1)
        print "\nBudget B = %d" % B
        print '####################'
        while l>=0 and minutes(time.time())< runtime:
            n=eta**l
            if B/n/max(1,numpy.ceil(log_eta(n)))>=min_unit and n >=min_arms:
                if max_unit is None or B/max(1,numpy.ceil(log_eta(n)))<=max_unit:
                    print 's=%d, n=%d' %(l,n)
                    print 'n_i\tr_k'
                    print "time elapsed: "+ str(minutes(time.time()))
                    arms,result = sha_inf(model,params,units,dir, n,B,eta,calculate)
                    if calculate:
                        results_dict[(k,l)]=arms
                        best_acc = max(best_acc,result[2])
                        print "k="+str(k)+", l="+str(l)+", val_acc="+str(result[2])+", test_acc="+str(result[3])+" best_arm_dir: " + result[0]['dir']
                        time_test.append([minutes(time.time()),best_acc])
                        print "time elapsed: " + str(minutes(time.time()))
            l-=1
            if calculate:
                pickle.dump([time_test,results_dict],open(dir+'/results_inf.pkl','w'))
        k+=1


def main(argv):

    model=''
    data_dir=''
    output_dir=''
    seed_id=0
    device_id=0
    try:
        opts, args = getopt.getopt(argv,"hm:i:o:s:d:",['model=','input_dir=','output_dir=','seed=','device='])
    except getopt.GetoptError:
        print 'hyperband_alg.py -m <model> -i <data_dir> -o <output_dir> -s <rng_seed> -d <GPU_id>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'hyperband_alg.py -i <data_dir> -o <output_dir> -s <rng_seed> -d <GPU_id>'
            sys.exit()
        elif opt in ("-m", "--model"):
            model = arg
        elif opt in ("-i", "--input_dir"):
            data_dir = arg
        elif opt in ("-o", "--output_dir"):
            output_dir = arg
        elif opt in ("-s", "--seed"):
            seed_id = int(arg)
        elif opt in ("-d", "--device"):
            device_id= int(arg)
    dir=output_dir+'/trial'+str(seed_id)
    if not os.path.exists(dir):
        os.makedirs(dir)
    sys.stdout = Logger(dir)
    if model=='cifar10':
        from cifar10.cifar10_helper import get_cnn_search_space,cifar10_conv
        params = get_cnn_search_space()
        obj=cifar10_conv(data_dir,device=device_id,seed=seed_id)
        hyperband_inf(obj,720,'iter',dir,params,4,max_k=3,starting_b=60000,min_unit=100,min_arms=4,calculate=True)

if __name__=="__main__":
    main(sys.argv[1:])
