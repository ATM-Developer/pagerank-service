import os
import tarfile


class TarUtil:

    @staticmethod
    def tar_files(tar_file_name, tar_dir_list=[], model="w:gz"):
        tar_file_list = []
        for tdl in tar_dir_list:
            for i in os.listdir(tdl):
                tar_file_list.append(os.path.join(tdl, i))
        tar_file_list = sorted(tar_file_list)
        with tarfile.open(tar_file_name, model) as tar_obj:
            # tar files
            for tmp_file in tar_file_list:
                tar_obj.add(tmp_file)

    @staticmethod
    def get_tar_files(tar_file_name, model="r"):
        files = []
        with tarfile.open(tar_file_name, model) as tar_obj:
            all_file_list = tar_obj.getmembers()
            for tmp_file in all_file_list:
                files.append(tmp_file.name)
        return files

    @staticmethod
    def untar(tar_file_name, path, model="r:gz"):
        with tarfile.open(tar_file_name, model) as tar_obj:
            members = tar_obj.getmembers()
            for member in members:
                if 'total_earnings' in member.name and not member.name.endswith('total_earnings'):
                    member.name = '/'.join(path.split('/') + member.name.split('/')[-2:])
                else:
                    member.name = '/'.join(path.split('/') + member.name.split('/')[-1:])
                tar_obj.extract(member.name)
