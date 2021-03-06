import torch
import torch.nn as nn
import numpy as np
import torch.optim as optim
import torch.backends.cudnn as cudnn
import torchvision.utils as vutils
import torchvision
import os
import argparse
import csnet
from torchvision import datasets,transforms
from torch.autograd import Variable
from torch.nn import init

parser = argparse.ArgumentParser(description='CSNet')
parser.add_argument('--dataset',default='own_image')
parser.add_argument('--textpath', help='path to textset', default='test_img/')
parser.add_argument('--batch-size',type=int,default=1,metavar='N')
parser.add_argument('--image-size',type=int,default=256,metavar='N')
parser.add_argument('--cuda',action='store_true',default=True)
parser.add_argument('--ngpu',type=int,default=1,metavar='N')
parser.add_argument('--seed',type=int,default=1,metavar='S')
parser.add_argument('--log-interval',type=int,default=100,metavar='N')
parser.add_argument('--outf',default='./results')
parser.add_argument('--cr',type=int,default=20)
opt = parser.parse_args()

if torch.cuda.is_available() and not opt.cuda:
    print("please run with GPU")
# print(opt)
if opt.seed is None:
    opt.seed = np.random.randint(1,10000)
print('Random seed: ',opt.seed)
np.random.seed(opt.seed)
torch.manual_seed(opt.seed)
if opt.cuda:
    torch.cuda.manual_seed(opt.seed)
criterion_mse = nn.MSELoss()
cudnn.benchmark = True

def data_loader():
    kwopt = {'num_workers': 8, 'pin_memory': True} if opt.cuda else {}
    transforms = torchvision.transforms.Compose([
                    torchvision.transforms.Resize(opt.image_size),
                    torchvision.transforms.Grayscale(num_output_channels=1),
                    torchvision.transforms.CenterCrop(opt.image_size),
                    torchvision.transforms.ToTensor(),
                    # torchvision.transforms.Normalize((0.5,0.5,0.5),(0.5,0.5,0.5))
                                        ])
    dataset = torchvision.datasets.ImageFolder(opt.textpath,transform=transforms)
    test_loader = torch.utils.data.DataLoader(dataset,batch_size = opt.batch_size,shuffle = False,**kwopt)
    return test_loader

def evaluation(testloader):
    input, _ = testloader.__iter__().__next__()
    input = input.numpy()
    sz_input = input.shape
    channels = sz_input[1]
    img_size = sz_input[3]

    target = torch.FloatTensor(opt.batch_size,channels,img_size,img_size)
    input = torch.FloatTensor(opt.batch_size,channels,img_size,img_size)

    CSnet = csnet.CSNET(channels,opt.cr)

    if opt.cuda:
        device_id = [0]
        CSnet = nn.DataParallel(CSnet.cuda(),device_ids = device_id)
        criterion_mse.cuda()
        target = target.cuda()
        input = input.cuda()

    model_iter = 16

    model_path = '%s/cr%s/model/%d.pth' % (opt.outf,opt.cr,model_iter)

    CSnet.load_state_dict(torch.load(model_path))

    CSnet.eval()

    csnet_mse_total = 0
    for idx, (data, _) in enumerate(testloader, 0):
        if data.size(0) != opt.batch_size:
            continue
        data_array = data.numpy()
        for i in range(opt.batch_size):
            target[i] = torch.from_numpy(data_array[i])

            for j in range(channels):
                input[i,j,:,:] = target[i,j,:,:]

        with torch.no_grad():
            target_var = Variable(target)
            input_var = Variable(input)
            output = CSnet(input_var,opt.batch_size,opt.ngpu)

            csnet_mse = criterion_mse(output,target_var)
            csnet_mse_total += csnet_mse

        if idx % 20 == 0:
            print('Test:[%d/%d] mse:%.4f \n' % (idx,len(testloader),csnet_mse.item()))


        vutils.save_image(target_var.data,'own_test_useless/orig_%d.bmp'% (idx), padding=0)
        vutils.save_image(output.data,'own_test_useless/recon_%d.bmp' % (idx), padding=0)

    print('Test: average mse: %.4f,' % (csnet_mse_total.item() / len(testloader)))

def main():
    test_loader = data_loader()
    evaluation(test_loader)

if __name__ == '__main__':
    main()