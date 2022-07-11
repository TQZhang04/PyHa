import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt

from sklearn import metrics


def annotation_chunker(kaleidoscope_df, chunk_length):
    """
    Function that converts a Kaleidoscope-formatted Dataframe containing 
    annotations to uniform chunks of chunk_length.

    Note: if all or part of an annotation covers the last < chunk_length
    seconds of a clip it will be ignored. If two annotations overlap in 
    the same 3 second chunk, both are represented in that chunk

    Args:
        kaleidoscope_df (Dataframe)
            - Dataframe of annotations in kaleidoscope format

        chunk_length (int)
            - duration to set all annotation chunks
    Returns:
        Dataframe of labels with chunk_length duration 
        (elements in "OFFSET" are divisible by chunk_length).
    """

    #Init list of clips to cycle through and output dataframe
    kaleidoscope_df["FILEPATH"] =  kaleidoscope_df["FOLDER"] + kaleidoscope_df["IN FILE"] 
    clips = kaleidoscope_df["FILEPATH"].unique()
    df_columns = {'FOLDER': 'str', 'IN FILE' :'str', 'CLIP LENGTH' : 'float64', 'CHANNEL' : 'int64', 'OFFSET' : 'float64',
                'DURATION' : 'float64', 'SAMPLE RATE' : 'int64','MANUAL ID' : 'str'}
    output_df = pd.DataFrame({c: pd.Series(dtype=t) for c, t in df_columns.items()})
    
    # going through each clip
    for clip in clips:
        clip_df = kaleidoscope_df[kaleidoscope_df["FILEPATH"] == clip]
        path = clip_df["FOLDER"].unique()[0]
        file = clip_df["IN FILE"].unique()[0]
        birds = clip_df["MANUAL ID"].unique()
        sr = clip_df["SAMPLE RATE"].unique()[0]
        clip_len = clip_df["CLIP LENGTH"].unique()[0]

        # quick data sanitization to remove very short clips
        # do not consider any chunk that is less than chunk_length
        if clip_len < chunk_length:
            continue
        potential_annotation_count = int(clip_len)//int(chunk_length)

        # going through each species that was ID'ed in the clip
        arr_len = int(clip_len*1000)
        for bird in birds:
            species_df = clip_df[clip_df["MANUAL ID"] == bird]
            human_arr = np.zeros((arr_len))
            # looping through each annotation
            for annotation in species_df.index:
                minval = int(round(species_df["OFFSET"][annotation] * 1000, 0))
                # Determining the end of a human label
                maxval = int(
                    round(
                        (species_df["OFFSET"][annotation] +
                         species_df["DURATION"][annotation]) *
                        1000,
                        0))
                # Placing the label relative to the clip
                human_arr[minval:maxval] = 1
            # performing the chunk isolation technique on the human array

            for index in range(potential_annotation_count):
                chunk_start = index * (chunk_length*1000)
                chunk_end = min((index+1)*chunk_length*1000,arr_len)
                chunk = human_arr[int(chunk_start):int(chunk_end)]
                if max(chunk) >= 0.5:
                    row = pd.DataFrame(index = [0])
                    annotation_start = chunk_start / 1000
                    #updating the dictionary
                    row["FOLDER"] = path
                    row["IN FILE"] = file
                    row["CLIP LENGTH"] = clip_len
                    row["OFFSET"] = annotation_start
                    row["DURATION"] = chunk_length
                    row["SAMPLE RATE"] = sr
                    row["MANUAL ID"] = bird
                    row["CHANNEL"] = 0
                    output_df = pd.concat([output_df,row], ignore_index=True)
    return output_df

def convert_label_to_local_score(manual_df, size_of_local_score):
    duration_of_clip = manual_df.iloc[0]["CLIP LENGTH"]
    seconds_per_index = duration_of_clip/size_of_local_score
    local_score = np.zeros(size_of_local_score)
    for i in range(size_of_local_score):
        current_seconds = i * seconds_per_index
        annotations_at_time = manual_df[(manual_df["OFFSET"] <= current_seconds) & (manual_df["OFFSET"] +manual_df["DURATION"] >=  current_seconds)]
        if (not annotations_at_time.empty):
            local_score[i] = 1
    
    return local_score

# TO DO: Wrapper Function to convert lable to local_scores array for whole dataset, 
def get_target_annotations(chunked_manual_df, chunk_size):
    target_score_array = []
    manual_df = chunked_manual_df.set_index(["FOLDER","IN FILE"])
    chunk_size_list = []
    for item in np.unique(manual_df.index):
        clip_df = chunked_manual_df[(chunked_manual_df["FOLDER"] == item[0]) & (chunked_manual_df["IN FILE"] == item[1])]
        print(item[1])
        clip_duration = clip_df.iloc[0]["CLIP LENGTH"]
        number_of_chunks = math.floor(clip_duration/chunk_size)
        target_score_clip = convert_label_to_local_score(clip_df, number_of_chunks)
        chunk_size_list.append((number_of_chunks, clip_duration, item[1]))
        target_score_array.extend(target_score_clip)
        #print(len(target_score_array))
    return np.array(target_score_array), chunk_size_list

# #Remember to chunk before passing it in
# target_array = get_target_annotations(chunked_df_manual_clip, 3)
# #Returns array -> 1 = bird, 0 = no bird

#instead here get the local scores array from generated_automated_labels dictionary 
def get_confidence_array(local_scores_array,chunked_df, chunk_size_list):
    array_of_max_scores = []
    manual_df = chunked_df.set_index(["FOLDER","IN FILE"])
    k = 0
    for item in np.unique(manual_df.index):
        #print(item[1])
        clip_df = chunked_df[(chunked_df["FOLDER"] == item[0]) & (chunked_df["IN FILE"] == item[1])]
        local_score_clip = local_scores_array[item[1]]
        duration_of_clip = clip_df.iloc[0]["CLIP LENGTH"] 
        num_chunks = math.floor(duration_of_clip/3) 
        if (num_chunks != chunk_size_list[k][0]):
            print("BAD CHUNK SIZE, CONFIDENCE SIZE: ", num_chunks, " TARGET: ", chunk_size_list[k] )
            print("duration_of_clip", duration_of_clip, chunk_size_list[i][1])
            print(item[1], chunk_size_list[k][2])
            break
        k += 1


        chunk_length = int(clip_df.iloc[0]["DURATION"]) #3 sec

        #chunk_count = math.floor(duration_of_clip / (clip_df["DURATION"][0]))
        #end_of_chunk = int(clip_df.iloc[-1]["OFFSET"])
        
        #DOES THIS MISS THE LAST CHUNK?
        for i in range(0, num_chunks * chunk_length,chunk_length):
            # now iterate through the local_score array for each chunk
            clip_length = clip_df.iloc[0]["CLIP LENGTH"]
            seconds_per_index = clip_length/len(local_score_clip)
            index_per_seconds = len(local_score_clip)/clip_length
            
            start_index = math.floor(index_per_seconds * i)
            end_index = math.floor(index_per_seconds *(i + chunk_length))
            # this for loop should interate throught the local score array per chunk 
            max_score = 0.0
            current_score = 0.0
            chunk_length = int(clip_df.iloc[0]["DURATION"])

            #print(start_index, end_index, len(local_score_clip),end_index - start_index )
            for j in range(start_index, end_index):
                    
                    #current_seconds = math.floor(j * seconds_per_index)
                    current_score = local_score_clip[j]
                    if (current_score > max_score):
                        
                        max_score = current_score
                        
            array_of_max_scores.append(max_score)
        #print(len(max_score))
    return array_of_max_scores

#wrapper function for get_confidence_array()
#i don't think this should be local_scores
def generate_ROC_curves(automated_df, manual_df, local_scoress, chunk_length = 3, label=""):
    """
    psuedocode
    1. chunked the data frames
    2. get the target array and new local score array 
    3. call the the ski-learn ROC function 
    """

    #MAKE SURE WE INCLUDE FILES SHARED IN BOTH
    #DO WE WANT TO IGNORE THIS???? BECUASE WE ARE MISSING FALSE NEGATIVES THIS WAY
    manual_df = manual_df[manual_df['IN FILE'].isin(automated_df["IN FILE"].to_list())]
    automated_df = automated_df[automated_df['IN FILE'].isin(manual_df["IN FILE"].to_list())]

    print(len(np.unique(manual_df['IN FILE'])))
    print(len(np.unique(automated_df['IN FILE'])))

    #CHUNK THE DATA
    auto_chunked_df = annotation_chunker(automated_df, chunk_length)
    manual_chunked_df = annotation_chunker(manual_df, chunk_length)

    auto_chunked_df = auto_chunked_df.sort_values(by="IN FILE")
    manual_chunked_df = manual_chunked_df.sort_values(by="IN FILE")
    #GENERATE TARGET AND CONFIDENCE ARRAYS FOR ROC CURVE GENERATION
    target_array, chunk_size_list = get_target_annotations(manual_chunked_df, chunk_length)
    confidence_scores_array = get_confidence_array(local_scoress,manual_chunked_df, chunk_size_list) #auto_chunked_df
    print("target", len(target_array))
    print("confidence", len(confidence_scores_array))

    #GENERATE AND PLOT ROC CURVES
    fpr, tpr, thresholds = metrics.roc_curve(target_array, confidence_scores_array) 
    roc_auc = metrics.auc(fpr, tpr)
    display = metrics.RocCurveDisplay(fpr=fpr, tpr=tpr, roc_auc=roc_auc)
    plt.plot(fpr, tpr, label=label)
    plt.ylabel("True Postives")
    plt.xlabel("False Positives ")
    plt.legend(loc="lower right")
    plt.show


#wrapper function for get_confidence_array()
#i don't think this should be local_scores
def generate_ROC_curves_raw_local(automated_df, manual_df, local_scoress, chunk_length = 3):
    """
    psuedocode
    1. chunked the data frames
    2. get the target array and new local score array 
    3. call the the ski-learn ROC function 
    """

    #MAKE SURE WE INCLUDE FILES SHARED IN BOTH
    #DO WE WANT TO IGNORE THIS???? BECUASE WE ARE MISSING FALSE NEGATIVES THIS WAY
    manual_df = manual_df[manual_df['IN FILE'].isin(automated_df["IN FILE"].to_list())]
    
    target_array = np.array([])
    confidence_scores_array = np.array([])
   
    tmp_df = manual_df.set_index(["FOLDER","IN FILE"])
    for item in np.unique(tmp_df.index):
        clip_manual_df = manual_df[(manual_df["FOLDER"] == item[0]) & (manual_df["IN FILE"] == item[1])]
        local_score_clip = local_scoress[item[1]]
        duration_of_clip = clip_manual_df.iloc[0]["CLIP LENGTH"]
        size_of_local_score = len(local_score_clip)
        seconds_per_index = duration_of_clip/size_of_local_score


        target_clip = np.zeros((size_of_local_score))
        for i in range(size_of_local_score):
            current_seconds = i * seconds_per_index
            annotations_at_time = manual_df[(manual_df["OFFSET"] <= current_seconds) & (manual_df["OFFSET"] +manual_df["DURATION"] >=  current_seconds)]
            if (not annotations_at_time.empty):
                target_clip[i] = 1
        target_array = np.append(target_array, target_clip)
        confidence_scores_array = np.append(confidence_scores_array, local_score_clip)
    
    print("target", len(target_array.tolist()))
    print("confidence", len(confidence_scores_array.tolist()))

    #GENERATE AND PLOT ROC CURVES
    fpr, tpr, thresholds = metrics.roc_curve(target_array, confidence_scores_array) 
    roc_auc = metrics.auc(fpr, tpr)
    display = metrics.RocCurveDisplay(fpr=fpr, tpr=tpr, roc_auc=roc_auc)
    plt.plot(fpr, tpr)
    plt.ylabel("True Postives")
    plt.xlabel("False Positives ")
    #display.plot()
    plt.show    

#def generate_ROC_curves_IOU(automated_df, manual_df, stats_df, chunk_length = 3):
#    """
#    psuedocode
#    1. chunked the data frames
#    2. get the target array and new local score array 
#    3. call the the ski-learn ROC function 
#    """
#    #CHUNK THE DATA
#    auto_chunked_df = annotation_chunker(automated_df, chunk_length)
#    manual_chunked_df = annotation_chunker(manual_df, chunk_length)#
#
#    #MAKE SURE WE INCLUDE FILES SHARED IN BOTH
#    #DO WE WANT TO IGNORE THIS???? BECUASE WE ARE MISSING FALSE NEGATIVES THIS WAY
#    auto_chunked_df = auto_chunked_df[auto_chunked_df['IN FILE'].isin(manual_chunked_df["IN FILE"].to_list())]
#    manual_chunked_df = manual_chunked_df[manual_chunked_df['IN FILE'].isin(auto_chunked_df["IN FILE"].to_list())]#
#
#    #GENERATE TARGET AND CONFIDENCE ARRAYS FOR ROC CURVE GENERATION
#    target_array = get_target_annotations(manual_chunked_df, chunk_length)
#    confidence_scores_array = get_confidence_array(local_scoress,auto_chunked_df)
#    print("target", target_array)
#    print("confidence", confidence_scores_array)
#
#    #GENERATE AND PLOT ROC CURVES
#    fpr, tpr, thresholds = metrics.roc_curve(target_array, confidence_scores_array) 
#    roc_auc = metrics.auc(fpr, tpr)
#    #display = metrics.RocCurveDisplay(fpr=fpr, tpr=tpr, roc_auc=roc_auc)
#    plt.plot(fpr, tpr)
#    plt.ylabel("True Postives")
#    plt.xlabel("False Positives ")
#    #display.plot()
#    plt.show    




