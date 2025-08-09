#!/usr/bin/env python3


import argparse
import glob
import os
import re
import sys
import wave

def main():
    parser = argparse.ArgumentParser(description="Merge split WAV chunks into one file.")
    parser.add_argument("dir", help="Directory containing wav chunks (e.g., /.../audio/<classId>)")
    parser.add_argument("--pattern", default="audio-*.wav", help="Glob pattern for chunks (default: audio-*.wav)")
    parser.add_argument("--out", default="merged.wav", help="Output file name (default: merged.wav)")
    args = parser.parse_args()

    dir_path = os.path.abspath(args.dir)
    out_path = os.path.join(dir_path, args.out)

    print("dir_path : ", dir_path)
    print("out_path : ", out_path)

    
    #paths = list_wavs(dir_path, args.pattern)
    #merge_wavs(paths, out_path)

    print(out_path)
    print(os.getcwd())
    print(" hi")
    
if __name__ == "__main__":
    main()


