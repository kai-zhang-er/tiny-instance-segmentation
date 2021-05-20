'''
evaluate the affine matching results
using matched points to calculate the transformation matrix and register the images,
then predict the location of corresponding points in target image
'''
import numpy as np
import xml.etree.ElementTree as ET
from scipy.spatial.kdtree import KDTree
import os
from align_transform import Align
from pycm import *
import matplotlib.pyplot as plt
import cv2


dataset="/media/ck/B6DAFDC2DAFD7F45/program/pyTuft/tiny-instance-segmentation/dataset/JPEGImages/"
annotation_dir="/media/ck/B6DAFDC2DAFD7F45/program/pyTuft/tiny-instance-segmentation/dataset/Annotations/"
downsample_ratio=2

def parse_xml(xml_path):
    """parse xml file and calculate center point of each bounding box

    Args:
        xml_path (str): path of xml file

    Returns:
        str: dict variable includes center points and id of the bounding box
    """
    box_dict={}
    tree = ET.parse(xml_path)
    for obj in tree.findall("object"):
        cls = "tuft"
        bbox = obj.find("bndbox")
        bbox = [float(bbox.find(x).text) for x in ["xmin", "ymin", "xmax", "ymax"]]
        center_point=[(bbox[0]+bbox[2])/2//downsample_ratio,(bbox[1]+bbox[3])/2//downsample_ratio] # x, y, downsample ratio=5
        box_dict.setdefault(obj.find("name").text, center_point)

    return box_dict


def parse_xml_box(xml_path):
    """parse xml file and calculate left top point and right bottom point of each bounding box

    Args:
        xml_path (str): path of xml file

    Returns:
        str: dict variable includes box coordinates and id of the bounding box
    """
    box_dict={}
    tree = ET.parse(xml_path)
    for obj in tree.findall("object"):
        cls = "tuft"
        bbox = obj.find("bndbox")
        bbox = [float(bbox.find(x).text)//downsample_ratio for x in ["xmin", "ymin", "xmax", "ymax"]] # top_left(x, y) right_bottom(x,y), downsample ratio=5
        box_dict.setdefault(obj.find("name").text, bbox)

    return box_dict


def xml_to_txt_pascalvoc(xml_id):
    xml_dict=parse_xml_box(annotation_dir+xml_id+".xml")

    with open("gt_txt/{}.txt".format(xml_id),"w") as f:
        for k in xml_dict.keys():
            f.write("{} {} {} {} {}\n".format(k, int(xml_dict[k][0]),int(xml_dict[k][1]),int(xml_dict[k][2]),int(xml_dict[k][3])))


def predict(pred_image_name, draw=False, save_result=False):
    """predict the location of tufts in pred_image

    Args:
        pred_image_name (str): id of target image
        draw (bool): whether to draw the result
    """
    ref_image_path=dataset+'DSC_2410.JPG' # source/reference image path
    ref_xml=parse_xml_box(annotation_dir+'DSC_2410.xml')  # reference image bounding box
    ref_xml_array=np.array(list(ref_xml.values()))
    
    target_image_path = dataset+pred_image_name+'.JPG'        # target image/image to be predicted
    
    # calculate the tranformation matrix and predict the corresponding points
    a=Align(ref_image_path,target_image_path,threshold=1, downsample_ratio=downsample_ratio)
    left_top_array, right_bottom_array=a.align_box(ref_xml_array.T, draw)

    keys=list(ref_xml.keys())

    if save_result:
        f_pred=open("pred_txt/{}.txt".format(pred_image_name),"w")
        for i in range(left_top_array.shape[1]):
            lt_x=int(left_top_array[0,i])
            lt_y=int(left_top_array[1,i])
            rb_x=int(right_bottom_array[0,i])
            rb_y=int(right_bottom_array[1,i])
            if lt_x>=0 and lt_y>=0 and rb_x<3000//downsample_ratio and rb_y<2000//downsample_ratio:
                f_pred.write("{} 1 {} {} {} {}\n".format(keys[i], lt_x, lt_y, rb_x, rb_y))

        f_pred.close()

    if draw:
        img_target=a.read_image(target_image_path)
        for i in range(left_top_array.shape[1]):
            lt_x=int(left_top_array[0,i])
            lt_y=int(left_top_array[1,i])
            rb_x=int(right_bottom_array[0,i])
            rb_y=int(right_bottom_array[1,i])
            color = list(np.random.random(size=3) * 256)
            if lt_x>=0 and lt_y>=0 and rb_x<3000//downsample_ratio and rb_y<2000//downsample_ratio:
                cv2.rectangle(img_target,(lt_x,lt_y),(rb_x,rb_y),color,1)
                cv2.putText(img_target,keys[i],(lt_x,lt_y-4),0,0.3,color)
        # show image
        cv2.imshow("result",img_target)
        cv2.waitKey(0)
        # save image
        # cv2.imwrite("result/{}.jpg".format(pred_image_name), img_target)


def evaluate(pred_image_name):
    """evaluate the transformation performance

    Args:
        pred_image_name (str): the target image id

    Returns:
        list: annotated class
        list: predicted class 
    """
    ref_image_path=dataset+'DSC_2410.JPG' # source/reference image path
    ref_xml=parse_xml(annotation_dir+'DSC_2410.xml')  # reference image bounding box
    
    # check if the annotation file exists
    if not os.path.isfile(annotation_dir+pred_image_name+'.xml'):
        return None,None

    target_image_path = dataset+pred_image_name+'.JPG'        # target image/image to be predicted
    target_xml=parse_xml(annotation_dir+pred_image_name+'.xml')  # target image annotations, used for evaluation
    ref_xml_array=np.array(list(ref_xml.values()))
    target_xml_array=np.array(list(target_xml.values()))

    # calculate the tranformation matrix and predict the corresponding points
    a=Align(ref_image_path,target_image_path,threshold=1, downsample_ratio=downsample_ratio)
    transformed_array=a.align_points(ref_xml_array.T)

    ref_keys=list(ref_xml.keys())
    target_keys=list(target_xml.keys())

    box_tree2=KDTree(target_xml_array)  # a KD-tree to search for the nearest annotations

    correct_num=0 # correct prediction
    matching_dist=[] # matching distance 
    predict_keys=[] # predict result

    for i in range(transformed_array.shape[1]):
        dist1, ind=box_tree2.query(transformed_array[:,i].T,k=1) # choose the nearest point of predicted result
        predict_keys.append(target_keys[ind])
        if ref_keys[i]==target_keys[ind]: #check if the class info is the same
            correct_num+=1
            matching_dist.append(dist1) # store the distance for each pair of matching

    print("correct/total: {}/{}, rate: {}".format(correct_num,len(target_keys),correct_num/len(target_keys)))
    print("total tufts: xml1({}),xml2({})".format(len(ref_keys),len(target_keys)))
    
    return ref_keys, predict_keys


def generate_evaluation_txt():
    '''
    generate the txt file to store the prediction results
    '''
    os.makedirs("pred_txt/", exist_ok=True)
    os.makedirs("gt_txt/", exist_ok=True)

    total_files=0
    for i in range(1300):
        pred_id="DSC_{}".format(2411+i)
        print("test DSC_{}".format(2411+i))
        # check if the annotation file exists
        if not os.path.isfile(annotation_dir+pred_id+'.xml'):
            print("no file"+ annotation_dir+pred_id+'.xml')
            continue
        total_files+=1
        predict("DSC_{}".format(2411+i), save_result=True) # save txt
        # predict("DSC_{}".format(2411+i), draw=True, save_result=False) # save pred image
        xml_to_txt_pascalvoc(pred_id)
    print("total {} files".format(total_files))


if __name__=="__main__":
    EVALUATION=False
    metric="box" # box or point
    if EVALUATION:
        if metric=="point":
            total_ref=[]
            total_predict=[]
            for i in range(1300):
                print("test DSC_{}".format(2411+i))
                ref_keys, predict_keys=evaluate("DSC_{}".format(2411+i))
                if ref_keys is None:
                    continue
                total_ref+=ref_keys
                total_predict+=predict_keys
            
            print("--------final confusion matrix--------")
            cm = ConfusionMatrix(actual_vector=total_ref, predict_vector=total_predict)
            print("Accuracy: {}, Recall: {}, Precision:{}, F1: {}".format(cm.Overall_ACC, cm.TPR_Macro,cm.PPV_Macro, cm.F1_Macro))
            cm.plot(cmap=plt.cm.Greens,number_label=True,plot_lib="matplotlib")
            plt.show()
        elif metric=="box":
            generate_evaluation_txt()
    else:
        image_name="DSC_2496"
        predict(image_name, draw=True)
        

    