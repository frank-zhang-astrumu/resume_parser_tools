# pylint: disable=invalid-name
"""
    This script is entrypoint of resume parser
"""
from __future__ import division
import nltk
import re
import os
from datetime import date
import docx2txt
import pandas as pd
from tika import parser
import phonenumbers
import pdfplumber
import logging

import spacy
from spacy.matcher import Matcher
from spacy.matcher import PhraseMatcher

import sys
import operator
import string
from stemming.porter2 import stem

from flask import Flask, request, jsonify
from flask_request_id_header.middleware import RequestID

from pythonjsonlogger import jsonlogger
from werkzeug.utils import secure_filename

AIE_APP = Flask(__name__)


class resumeparse(object):
    """
    This class is entrypoint of resume parser
    """
    work_and_employment = (
        'employment history',
        'work history',
        'work experience',
        'experience',
        'professional experience',
        'professional background',
        'additional experience',
        'career related experience',
        'related experience',
        'programming experience',
        'freelance',
        'freelance experience',
        'army experience',
        'military experience',
        'military background',
    )

    education_and_training = (
        'academic background',
        'academic experience',
        'programs',
        'courses',
        'related courses',
        'education',
        'educational background',
        'educational qualifications',
        'educational training',
        'education and training',
        'training',
        'academic training',
        'professional training',
        'course project experience',
        'related course projects',
        'internship experience',
        'internships',
        'apprenticeships',
        'college activities',
        'certifications',
        'special training',
    )

    skills_header = (
        'credentials',
        'qualifications',
        'areas of experience',
        'areas of expertise',
        'areas of knowledge',
        'skills',
        "other skills",
        "other abilities",
        'career related skills',
        'professional skills',
        'specialized skills',
        'technical skills',
        'computer skills',
        'personal skills',
        'computer knowledge',
        'technologies',
        'technical experience',
        'proficiencies',
        'languages',
        'language competencies and skills',
        'programming languages',
        'competencies'
    )

    misc = (
        'activities and honors',
        'activities',
        'affiliations',
        'professional affiliations',
        'associations',
        'professional associations',
        'memberships',
        'professional memberships',
        'athletic involvement',
        'community involvement',
        'refere',
        'civic activities',
        'extra-Curricular activities',
        'professional activities',
        'volunteer work',
        'volunteer experience',
        'additional information',
        'interests'
    )

    accomplishments = (
        'achievement',
        'licenses',
        'presentations',
        'conference presentations',
        'conventions',
        'dissertations',
        'exhibits',
        'papers',
        'publications',
        'professional publications',
        'research',
        'research grants',
        'project',
        'research projects',
        'personal projects',
        'current research interests',
        'thesis',
        'theses',
    )


    def convert_docx_to_txt(docx_file,docx_parser):
        """
            A utility function to convert a Microsoft docx files to raw text.
        """
        try:
            if docx_parser == "tika":
                text = parser.from_file(docx_file, service='text')['content']
            elif docx_parser == "docx2txt":
                text = docx2txt.process(docx_file)
            else:
                logging.error('Choose docx_parser from tika or docx2txt :: ' + str(e)+' is not supported')
                return [], " "
        except RuntimeError as e:
            logging.error('Error in tika installation:: ' + str(e))
            logging.error('--------------------------')
            logging.error('Install java for better result ')
            text = docx2txt.process(docx_file)
        except Exception as e:
            logging.error('Error in docx file:: ' + str(e))
            return [], " "
        try:
            clean_text = re.sub(r'\n+', '\n', text)
            clean_text = clean_text.replace("\r", "\n").replace("\t", " ")  # Normalize text blob
            resume_lines = clean_text.splitlines()  # Split text blob into individual lines
            resume_lines = [re.sub('\s+', ' ', line.strip()) for line in resume_lines if
                            line.strip()]  # Remove empty strings and whitespaces
            return resume_lines, text
        except Exception as e:
            logging.error('Error in docx file:: ' + str(e))
            return [], " "

    def convert_pdf_to_txt(pdf_file):
        """
        A utility function to convert a machine-readable PDF to raw text.
        """
        try:
            raw_text = parser.from_file(pdf_file, service='text')['content']
        except RuntimeError as e:
            logging.error('Error in tika installation:: ' + str(e))
            logging.error('--------------------------')
            logging.error('Install java for better result ')
            pdf = pdfplumber.open(pdf_file)
            raw_text= ""
            for page in pdf.pages:
                raw_text += page.extract_text() + "\n"
            pdf.close()
        except Exception as e:
            logging.error('Error in docx file:: ' + str(e))
            return [], " "
        try:
            full_string = re.sub(r'\n+', '\n', raw_text)
            full_string = full_string.replace("\r", "\n")
            full_string = full_string.replace("\t", " ")

            # Remove awkward LaTeX bullet characters

            full_string = re.sub(r"\uf0b7", " ", full_string)
            full_string = re.sub(r"\(cid:\d{0,2}\)", " ", full_string)
            full_string = re.sub(r'• ', " ", full_string)

            # Split text blob into individual lines
            resume_lines = full_string.splitlines(True)

            # Remove empty strings and whitespaces
            resume_lines = [re.sub('\s+', ' ', line.strip()) for line in resume_lines if line.strip()]

            return resume_lines, raw_text
        except Exception as e:
            logging.error('Error in docx file:: ' + str(e))
            return [], " "

    def find_segment_indices(string_to_search, resume_segments, resume_indices):
        """
        A utility function to find segment indeices.
        """
        for i, line in enumerate(string_to_search):

            if line[0].islower():
                continue

            header = line.lower()

            if [w for w in resumeparse.work_and_employment if header.startswith(w)]:
                try:
                    resume_segments['work_and_employment'][header]
                except:
                    resume_indices.append(i)
                    header = [w for w in resumeparse.work_and_employment if header.startswith(w)][0]
                    resume_segments['work_and_employment'][header] = i
            elif [e for e in resumeparse.education_and_training if header.startswith(e)]:
                try:
                    resume_segments['education_and_training'][header]
                except:
                    resume_indices.append(i)
                    header = [e for e in resumeparse.education_and_training if header.startswith(e)][0]
                    resume_segments['education_and_training'][header] = i
            elif [s for s in resumeparse.skills_header if header.startswith(s)]:
                try:
                    resume_segments['skills'][header]
                except:
                    resume_indices.append(i)
                    header = [s for s in resumeparse.skills_header if header.startswith(s)][0]
                    resume_segments['skills'][header] = i
            elif [m for m in resumeparse.misc if header.startswith(m)]:
                try:
                    resume_segments['misc'][header]
                except:
                    resume_indices.append(i)
                    header = [m for m in resumeparse.misc if header.startswith(m)][0]
                    resume_segments['misc'][header] = i
            elif [a for a in resumeparse.accomplishments if header.startswith(a)]:
                try:
                    resume_segments['accomplishments'][header]
                except:
                    resume_indices.append(i)
                    header = [a for a in resumeparse.accomplishments if header.startswith(a)][0]
                    resume_segments['accomplishments'][header] = i

    def slice_segments(string_to_search, resume_segments, resume_indices):
        """
        A utility function to slice the segments.
        """
        resume_segments['contact_info'] = string_to_search[:resume_indices[0]]

        for section, value in resume_segments.items():
            if section == 'contact_info':
                continue

            for sub_section, start_idx in value.items():
                end_idx = len(string_to_search)
                if (resume_indices.index(start_idx) + 1) != len(resume_indices):
                    end_idx = resume_indices[resume_indices.index(start_idx) + 1]

                resume_segments[section][sub_section] = string_to_search[start_idx:end_idx]

    def segment(string_to_search):
        """
        A utility function to segment.
        """
        resume_segments = {
            'work_and_employment': {},
            'education_and_training': {},
            'skills': {},
            'accomplishments': {},
            'misc': {}
        }

        resume_indices = []

        resumeparse.find_segment_indices(string_to_search, resume_segments, resume_indices)
        if len(resume_indices) != 0:
            resumeparse.slice_segments(string_to_search, resume_segments, resume_indices)
        else:
            resume_segments['contact_info'] = []

        return resume_segments

    def get_experience(resume_segments):
        """
        get the education experience.
        """
        total_exp = 0
        if len(resume_segments['work_and_employment'].keys()):
            text = ""
            for key, values in resume_segments['work_and_employment'].items():
                text += " ".join(values) + " "
            total_exp = resumeparse.calculate_experience(text)
            return total_exp, text
        else:
            text = ""
            for key in resume_segments.keys():
                if key != 'education_and_training':
                    if key == 'contact_info':
                        text += " ".join(resume_segments[key]) + " "
                    else:
                        for key_inner, value in resume_segments[key].items():
                            text += " ".join(value) + " "
            total_exp = resumeparse.calculate_experience(text)
            return total_exp, text
        return total_exp, " "

    def find_phone(text):
        """
        get the phtone number.
        """
        try:
            return list(iter(phonenumbers.PhoneNumberMatcher(text, None)))[0].raw_string
        except:
            try:
                return re.search(
                    r'(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})',
                    text).group()
            except:
                return ""

    def extract_email(text):
        """
        get the email infor.
        """
        email = re.findall(r"([^@|\s]+@[^@]+\.[^@|\s]+)", text)
        if email:
            try:
                return email[0].split()[0].strip(';')
            except IndexError:
                return None

    def extract_name(resume_text):
        """
        get the student name.
        """
        nlp_text = nlp(resume_text)
        pattern = [{'POS': 'PROPN'}, {'POS': 'PROPN'}]
        matcher.add('NAME', None, pattern)
        matches = matcher(nlp_text)
        for match_id, start, end in matches:
            span = nlp_text[start:end]
            return span.text
        return ""


    def extract_university(text):
        """
        get the univeristy name.
        """
        universities = [i.lower() for i in univeristy_df[1]]
        college_name = []
        listex = universities
        listsearch = [text.lower()]

        for i in range(len(listex)):
            for ii in range(len(listsearch)):

                if re.findall(listex[i], re.sub(' +', ' ', listsearch[ii])):

                    college_name.append(listex[i])

        return college_name

    def job_designition(text):
        """
        get the job title infor.
        """
        job_titles = []

        __nlp = nlp(text.lower())

        matches = designitionmatcher(__nlp)
        for match_id, start, end in matches:
            span = __nlp[start:end]
            job_titles.append(span.text)
        return job_titles

    def get_degree(text):
        """
        get the list of degree.
        """
        doc = custom_nlp2(text)
        degree = []

        degree = [ent.text.replace("\n", " ") for ent in list(doc.ents) if ent.label_ == 'Degree']
        return list(dict.fromkeys(degree).keys())

    def get_company_working(text):
        """
        get the work company.
        """
        doc = custom_nlp3(text)
        degree = []

        degree = [ent.text.replace("\n", " ") for ent in list(doc.ents)]
        return list(dict.fromkeys(degree).keys())

    def extract_skills(text):
        """
        get the skills list.
        """
        skills = []

        __nlp = nlp(text.lower())
        # Only run nlp.make_doc to speed things up
        matches = skillsmatcher(__nlp)
        for match_id, start, end in matches:
            span = __nlp[start:end]
            skills.append(span.text)
        skills = list(set(skills))
        return skills

    def read_file(file,docx_parser = "tika"):
        """
        file : Give path of resume file
        docx_parser : Enter docx2txt or tika, by default is tika
        """
        # file = "/content/Asst Manager Trust Administration.docx"
        file = os.path.join(file)
        if file.endswith('docx') or file.endswith('doc'):
            if file.endswith('doc') and docx_parser == "docx2txt":
                docx_parser = "tika"
                logging.error("doc format not supported by the docx2txt changing back to tika")
            resume_lines, raw_text = resumeparse.convert_docx_to_txt(file,docx_parser)
        elif file.endswith('pdf'):
            resume_lines, raw_text = resumeparse.convert_pdf_to_txt(file)
        elif file.endswith('txt'):
            with open(file, 'r', encoding='latin') as f:
                resume_lines = f.readlines()

        else:
            resume_lines = None
        resume_segments = resumeparse.segment(resume_lines)

        full_text = " ".join(resume_lines)

        email = resumeparse.extract_email(full_text)
        phone = resumeparse.find_phone(full_text)
        name = resumeparse.extract_name(" ".join(resume_segments['contact_info']))
        university = resumeparse.extract_university(full_text)

        designition = resumeparse.job_designition(full_text)
        designition = list(dict.fromkeys(designition).keys())

        degree = resumeparse.get_degree(full_text)
        company_working = resumeparse.get_company_working(full_text)

        skills = ""

        if len(resume_segments['skills'].keys()):
            for key , values in resume_segments['skills'].items():
                skills += re.sub(key, '', ",".join(values), flags=re.IGNORECASE)
            skills = skills.strip().strip(",").split(",")

        if len(skills) == 0:
            skills = resumeparse.extract_skills(full_text)
        skills = list(dict.fromkeys(skills).keys())

        return {
            "email": email,
            "phone": phone,
            "name": name,
            "university": university,
            "job role": designition,
            "degree": degree,
            "skills": skills,
            "Companies worked at": company_working
        }


# make Request IDs available to AIE_APP, and also send one back to the client.
AIE_APP.config['REQUEST_ID_UNIQUE_VALUE_PREFIX'] = 'mba_'
RequestID(AIE_APP)
AIE_LOGGER = logging.getLogger(__name__)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
AIE_LOGGER.addHandler(logHandler)
AIE_LOGGER.setLevel(logging.INFO)

ALLOWED_EXTENSIONS = set(['pdf', 'docx', 'doc', 'txt'])

def allowed_file(filename):
    '''
    this function of judge file type.
    '''
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in ALLOWED_EXTENSIONS

# AIE_APP.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024


# define the URL and path:
@AIE_APP.route('/resume-tools-owner', methods=['POST'])
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
# pylint: disable=too-many-locals
def resume_parsing():
    '''
    this function of resume parsing.
    '''
    request_id = request.environ.get("HTTP_X_REQUEST_ID")
    msg = {"infor": "files uploaded successfully"}

    if 'file' not in request.files:
        return {
            "Fatal，System exit": "there are no input files."
            "Request is aborted."
        }

    inputfiles = request.files.getlist("file")
    all_result = {}
    all_result['parsing_result'] = []
    for file in inputfiles:
        if file and allowed_file(file.filename):
            file_name = secure_filename(file.filename)
            upload_path = os.path.join('/upload/', file_name)
            file.save(upload_path)
            result_json = resumeparse.read_file(upload_path)
            if result_json:
                os.remove(upload_path)
            one_result_json = {}
            one_result_json["file_name"] = file_name
            one_result_json['parsing_result'] = result_json
            all_result['parsing_result'].append(one_result_json)
            # all_result = json.loads(all_result)

        else:
            msg = {"error": "failed to upload file"}
            return msg
    all_result["request_id"] = request_id
    all_result = jsonify(all_result)
    return all_result


if __name__ == '__main__':
    # load pre-trained model
    base_path = os.path.dirname(__file__)
    nlp = spacy.load('en_core_web_sm')
    custom_nlp2 = spacy.load(os.path.join(base_path,"degree","model"))
    custom_nlp3 = spacy.load(os.path.join(base_path,"company_working","model"))
    # initialize matcher with a vocab
    matcher = Matcher(nlp.vocab)
    #load pre define library
    title_file_path = os.path.join(base_path,"titles_combined.txt")
    title_file = open(title_file_path, "r", encoding='utf-8')
    designation = [line.strip().lower() for line in title_file]
    designitionmatcher = PhraseMatcher(nlp.vocab)
    patterns = [nlp.make_doc(text) for text in designation if len(nlp.make_doc(text)) < 10]
    designitionmatcher.add("Job title", None, *patterns)

    skills_file_path = os.path.join(base_path,"LINKEDIN_SKILLS_ORIGINAL.txt")
    skills_file = open(skills_file_path, "r", encoding='utf-8')
    skill = [line.strip().lower() for line in skills_file]
    skillsmatcher = PhraseMatcher(nlp.vocab)
    patterns = [nlp.make_doc(text) for text in skill if len(nlp.make_doc(text)) < 10]
    skillsmatcher.add("skills", None, *patterns)

    university_file_path = os.path.join(base_path,'world-universities.csv')
    univeristy_df = pd.read_csv(university_file_path, header=None)

    AIE_APP.run(host='0.0.0.0', debug=True, threaded=True)